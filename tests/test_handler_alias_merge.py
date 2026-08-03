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


# ── carry-forward continuity ────────────────────────────────────────────────

def _month_env(monkeypatch, tmp_path, *, rows, expenses, recovery_referrer, recovery_month):
    """A handler with candidates, a payout and one aliased recovery."""
    import json
    from features import handler_expenses as he, handler_salaries as hs
    from features import payment_verification_engine as pve

    _registry(monkeypatch, [
        {"id": "referrer-pavan", "name": "Pavan Kalyan", "aliases": ["LUKKA PAVAN KALYAN"]},
    ])
    (tmp_path / "s.json").write_text(json.dumps({"salaries": {}}), encoding="utf-8")
    (tmp_path / "e.json").write_text(json.dumps({"expenses": expenses}), encoding="utf-8")
    monkeypatch.setattr(hs, "_FILE", str(tmp_path / "s.json"))
    monkeypatch.setattr(he, "_FILE", str(tmp_path / "e.json"))
    monkeypatch.setattr(cs, "_load", lambda **_k: {"candidates": rows})
    monkeypatch.setattr(cs, "_stats_rows_deduped", lambda r: r)

    entry = {
        "referrer": recovery_referrer,
        "receiver_registry_name": recovery_referrer,
        "amount": 5_000,
        "total_payout_adjustment": 5_000,
        "payment_date": f"{recovery_month}-22",
        "status": "posted",
    }
    monkeypatch.setattr(
        pve, "ledger_entries",
        lambda month=None, action=None, **_k: (
            [entry] if (action in (None, "referrer_recovery")
                        and (month is None or month == recovery_month)) else []
        ),
    )
    monkeypatch.setattr(
        pve, "recovery_summary_by_referrer",
        lambda *, month=None: (
            {recovery_referrer.lower(): {
                "name": recovery_referrer, "total": 5_000, "count": 1,
                "commission_already_received": 0, "recoverable_company_share": 0,
            }} if month in (None, recovery_month) else {}
        ),
    )


def _pavan(month):
    for p in cs.stats(month).get("top_performers", []):
        if "pavan" in str(p.get("name", "")).lower():
            return p
    return None


def test_a_recovery_recorded_under_an_alias_is_counted_in_its_own_month(
    monkeypatch, tmp_path
):
    """It used to vanish from July and silently shrink August's opening."""
    _month_env(
        monkeypatch, tmp_path,
        rows=[{"id": "c1", "name": "X", "reference": "Pavan Kalyan", "payment": 10_000,
               "logged_date": "2026-07-05", "date": "2026-07-05", "stage": "in_progress"}],
        expenses=[],
        recovery_referrer="LUKKA PAVAN KALYAN",
        recovery_month="2026-07",
    )
    monkeypatch.setattr(cs, "referrer_commission_amount", lambda _r: 5_000)

    july = _pavan("2026-07")

    assert july is not None
    # The recovery belongs to the month it was posted in, on the canonical row.
    assert july["recoveries_total"] == 5_000


def test_opening_balance_equals_the_previous_month_closing(monkeypatch, tmp_path):
    """The governing rule: this month opens where last month closed."""
    _month_env(
        monkeypatch, tmp_path,
        rows=[{"id": "c1", "name": "X", "reference": "Pavan Kalyan", "payment": 10_000,
               "logged_date": "2026-07-05", "date": "2026-07-05", "stage": "in_progress"}],
        expenses=[{"id": "p1", "reference": "Pavan Kalyan", "amount": 6_000,
                   "category": "commission", "date": "2026-07-30"}],
        recovery_referrer="LUKKA PAVAN KALYAN",
        recovery_month="2026-07",
    )
    monkeypatch.setattr(cs, "referrer_commission_amount", lambda _r: 5_000)

    july = _pavan("2026-07")
    august = _pavan("2026-08")

    july_closing = july["net_payable"]
    assert august is not None
    assert august["prior_balance"] == july_closing, (
        f"August opened at {august['prior_balance']} but July closed at {july_closing}"
    )
    # And August opens where July closed rather than re-deriving a different number.
    assert august["net_payable"] == august["prior_balance"]


def test_the_recovery_is_applied_once_not_in_both_months(monkeypatch, tmp_path):
    # A payout keeps the carried balance non-zero, so August still has a row.
    _month_env(
        monkeypatch, tmp_path,
        rows=[{"id": "c1", "name": "X", "reference": "Pavan Kalyan", "payment": 10_000,
               "logged_date": "2026-07-05", "date": "2026-07-05", "stage": "in_progress"}],
        expenses=[{"id": "p1", "reference": "Pavan Kalyan", "amount": 6_000,
                   "category": "commission", "date": "2026-07-30"}],
        recovery_referrer="LUKKA PAVAN KALYAN",
        recovery_month="2026-07",
    )
    monkeypatch.setattr(cs, "referrer_commission_amount", lambda _r: 5_000)

    july = _pavan("2026-07")
    august = _pavan("2026-08")

    # Counted in July's own month; August sees it only through the opening
    # balance, never as a second deduction.
    assert july["recoveries_total"] == 5_000
    assert august["recoveries_total"] == 0
    assert august["prior_balance"] == july["net_payable"]
