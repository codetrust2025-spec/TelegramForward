"""One person must not appear as two handlers.

"Pavan Kalyan" and "LUKKA PAVAN KALYAN" are the same referrer. The registry
already recorded it — referrers.json lists LUKKA PAVAN KALYAN as an alias of
Pavan Kalyan, and the payment account under that holder name is linked to
referrer-pavan — but nothing consumed it. Reference buckets were built from the
raw string, so a single referrer_recovery ledger entry recorded against the
account-holder name created a second handler with its own opening balance.

No ledger row, expense, candidate or timestamp is rewritten to fix this: the
alias resolution happens when buckets are keyed.
"""

from __future__ import annotations

import pytest

from features import candidate_store as cs


@pytest.fixture(autouse=True)
def _clean_alias_cache():
    cs.reload_reference_aliases()
    yield
    cs.reload_reference_aliases()


def _registry(monkeypatch, rows):
    from features import referrer_registry as rr

    monkeypatch.setattr(rr, "list_referrers", lambda **_k: rows)
    cs.reload_reference_aliases()


def test_alias_resolves_to_the_canonical_handler(monkeypatch):
    _registry(monkeypatch, [
        {"id": "referrer-pavan", "name": "Pavan Kalyan",
         "aliases": ["Pawan Kalyan", "LUKKA PAVAN KALYAN"]},
    ])

    assert cs._reference_key("LUKKA PAVAN KALYAN") == "pavan kalyan"
    assert cs._reference_key("Lukka Pavan Kalyan") == "pavan kalyan"
    assert cs._reference_key("Pawan Kalyan") == "pavan kalyan"
    # The canonical spelling is unchanged.
    assert cs._reference_key("Pavan Kalyan") == "pavan kalyan"


def test_names_without_an_alias_are_untouched(monkeypatch):
    _registry(monkeypatch, [
        {"id": "referrer-pavan", "name": "Pavan Kalyan", "aliases": ["LUKKA PAVAN KALYAN"]},
    ])

    for name in ("Thrilok", "Venugopal", "Ravinder", "Charan"):
        assert cs._reference_key(name) == name.lower()
    assert cs._reference_key("") == "unknown"


def test_merged_row_is_labelled_with_the_canonical_name(monkeypatch):
    _registry(monkeypatch, [
        {"id": "referrer-pavan", "name": "Pavan Kalyan", "aliases": ["LUKKA PAVAN KALYAN"]},
    ])

    assert cs._canonical_reference_name("LUKKA PAVAN KALYAN") == "Pavan Kalyan"
    assert cs._canonical_reference_name("Thrilok") == "Thrilok"


def test_a_missing_registry_falls_back_to_raw_keys(monkeypatch):
    """The earnings screen must keep working if the registry cannot be read."""
    from features import referrer_registry as rr

    def _boom(**_kwargs):
        raise RuntimeError("registry unavailable")

    monkeypatch.setattr(rr, "list_referrers", _boom)
    cs.reload_reference_aliases()

    assert cs._reference_key("LUKKA PAVAN KALYAN") == "lukka pavan kalyan"
    assert cs._reference_key("Pavan Kalyan") == "pavan kalyan"


def test_recovery_against_an_alias_lands_on_the_canonical_handler(monkeypatch, tmp_path):
    """The exact production shape: recovery under the account-holder name."""
    import json
    from features import handler_expenses as he, handler_salaries as hs
    from features import payment_verification_engine as pve

    _registry(monkeypatch, [
        {"id": "referrer-pavan", "name": "Pavan Kalyan", "aliases": ["LUKKA PAVAN KALYAN"]},
    ])

    salary_path = tmp_path / "handler_salaries.json"
    salary_path.write_text(json.dumps({"salaries": {}}), encoding="utf-8")
    expense_path = tmp_path / "handler_expenses.json"
    expense_path.write_text(json.dumps({"expenses": []}), encoding="utf-8")
    monkeypatch.setattr(hs, "_FILE", str(salary_path))
    monkeypatch.setattr(he, "_FILE", str(expense_path))

    row = {
        "id": "c1", "name": "Candidate", "reference": "Pavan Kalyan",
        "payment": 20_000, "logged_date": "2026-06-15", "date": "2026-06-15",
        "stage": "in_progress",
    }
    monkeypatch.setattr(cs, "_load", lambda **_k: {"candidates": [row]})
    monkeypatch.setattr(cs, "_stats_rows_deduped", lambda r: r)
    monkeypatch.setattr(cs, "referrer_commission_amount", lambda _r: 10_000)
    monkeypatch.setattr(
        pve, "ledger_entries",
        lambda **_k: [{
            "referrer": "LUKKA PAVAN KALYAN",
            "receiver_registry_name": "LUKKA PAVAN KALYAN",
            "amount": 5_000,
            "payment_date": "2026-06-22",
        }],
    )

    carry = cs._carry_forward_balances("2026-07")

    assert "lukka pavan kalyan" not in carry, "alias must not form its own handler"
    assert "pavan kalyan" in carry
    pavan = carry["pavan kalyan"]
    assert pavan["prior_recoveries"] == 5_000
    # 10,000 earned - 5,000 recovered, on one handler rather than split across two.
    assert pavan["prior_balance"] == 5_000
    assert (
        pavan["prior_owed"] - pavan["prior_paid"] - pavan["prior_recoveries"]
        == pavan["prior_balance"]
    )


def test_no_financial_value_is_altered_by_the_merge(monkeypatch):
    """Merging changes which bucket a number lands in, never the number."""
    _registry(monkeypatch, [
        {"id": "referrer-pavan", "name": "Pavan Kalyan", "aliases": ["LUKKA PAVAN KALYAN"]},
    ])
    row = {"reference": "LUKKA PAVAN KALYAN", "payment": 20_000,
           "expected_payment": 20_000, "stage": "completed",
           "service_type": "profile_service"}

    # The commission for a row is computed from the row, not from the bucket.
    assert cs.referrer_commission_amount(row) == cs.referrer_commission_amount(
        {**row, "reference": "Pavan Kalyan"}
    )


# ── duplicate prevention on handler creation ────────────────────────────────

def _handler_env(monkeypatch, tmp_path, rows):
    import yaml
    from core import dashboard_auth_vps as auth

    path = tmp_path / "dashboard_handlers.yaml"
    path.write_text(yaml.safe_dump({"handlers": rows}), encoding="utf-8")
    monkeypatch.setattr(auth, "_handlers_yaml_path", lambda: str(path))
    return auth


def test_a_second_login_cannot_reuse_an_existing_reference(monkeypatch, tmp_path):
    auth = _handler_env(monkeypatch, tmp_path, [
        {"username": "pavan", "reference": "Pavan Kalyan", "password": "x"},
    ])

    err = auth.admin_add_handler("pavan2", "pavan kalyan", "y")

    assert err and "already belongs to handler 'pavan'" in err


def test_an_alias_is_rejected_as_a_new_reference(monkeypatch, tmp_path):
    auth = _handler_env(monkeypatch, tmp_path, [
        {"username": "pavan", "reference": "Pavan Kalyan", "password": "x"},
    ])
    from features import referrer_registry as rr

    monkeypatch.setattr(rr, "resolve_referrer", lambda value: (
        {"id": "referrer-pavan", "name": "Pavan Kalyan",
         "aliases": ["LUKKA PAVAN KALYAN"]}
        if str(value).strip().lower() in {"pavan kalyan", "lukka pavan kalyan"} else None
    ))

    err = auth.admin_add_handler("lukka", "LUKKA PAVAN KALYAN", "y")

    assert err and "alias of referrer 'Pavan Kalyan'" in err


def test_a_genuinely_new_handler_is_still_accepted(monkeypatch, tmp_path):
    auth = _handler_env(monkeypatch, tmp_path, [
        {"username": "pavan", "reference": "Pavan Kalyan", "password": "x"},
    ])
    from features import referrer_registry as rr

    monkeypatch.setattr(rr, "resolve_referrer", lambda _v: None)

    assert auth.admin_add_handler("newperson", "New Person", "z") is None


def test_creation_still_works_without_the_registry(monkeypatch, tmp_path):
    auth = _handler_env(monkeypatch, tmp_path, [])
    from features import referrer_registry as rr

    def _boom(_value):
        raise RuntimeError("registry unavailable")

    monkeypatch.setattr(rr, "resolve_referrer", _boom)

    assert auth.admin_add_handler("someone", "Some One", "z") is None
