"""An opening balance has to say where it came from.

The referrer earnings screen shows "Opening balance +5,000" for a month. That
figure is only actionable if the UI can also name the months behind it and the
earned/paid/recovered split, so `_carry_forward_balances` reports the months
that actually moved the number alongside the components.
"""

import json

from features import candidate_store, handler_expenses, handler_salaries
from features import payment_verification_engine


def _write_salary_store(tmp_path, salaries):
    path = tmp_path / "handler_salaries.json"
    path.write_text(json.dumps({"salaries": salaries}), encoding="utf-8")
    return str(path)


def _write_expenses(tmp_path, expenses):
    path = tmp_path / "handler_expenses.json"
    path.write_text(json.dumps({"expenses": expenses}), encoding="utf-8")
    return str(path)


def _arrange(monkeypatch, tmp_path, *, rows, expenses, salaries=None, ledger=None):
    monkeypatch.setattr(
        handler_salaries, "_FILE", _write_salary_store(tmp_path, salaries or {})
    )
    monkeypatch.setattr(
        handler_expenses, "_FILE", _write_expenses(tmp_path, expenses)
    )
    monkeypatch.setattr(candidate_store, "_load", lambda **_k: {"candidates": rows})
    monkeypatch.setattr(candidate_store, "_stats_rows_deduped", lambda r: r)
    monkeypatch.setattr(candidate_store, "referrer_commission_amount", lambda _r: 30_000)
    monkeypatch.setattr(
        payment_verification_engine, "ledger_entries", lambda **_k: list(ledger or [])
    )


def _row(row_id, date):
    return {
        "id": row_id,
        "name": "Candidate",
        "reference": "Thrilok",
        "payment": 60_000,
        "logged_date": date,
        "date": date,
        "stage": "in_progress",
    }


SALARY = {
    "thrilok": {
        "reference": "Thrilok",
        "monthly_salary": 15_000,
        "active_from": "2026-05",
    }
}


def test_reports_the_single_month_a_balance_came_from(monkeypatch, tmp_path):
    _arrange(
        monkeypatch,
        tmp_path,
        rows=[_row("june", "2026-06-15")],
        expenses=[
            {
                "id": "june-payout",
                "reference": "Thrilok",
                "amount": 40_000,
                "category": "commission",
                "date": "2026-06-30",
            }
        ],
        salaries=SALARY,
    )

    carry = candidate_store._carry_forward_balances("2026-07")["thrilok"]

    assert carry["prior_months"] == ["2026-06"]
    assert carry["prior_owed"] == 45_000  # 30,000 commission + 15,000 salary
    assert carry["prior_paid"] == 40_000
    assert carry["prior_balance"] == 5_000
    # The reported components must reconstruct the balance exactly, or the UI
    # explanation would contradict the figure it explains.
    assert (
        carry["prior_owed"] - carry["prior_paid"] - carry["prior_recoveries"]
        == carry["prior_balance"]
    )


def test_reports_every_contributing_month_in_order(monkeypatch, tmp_path):
    _arrange(
        monkeypatch,
        tmp_path,
        rows=[_row("june", "2026-06-15"), _row("march", "2026-03-10")],
        expenses=[
            {
                "id": "june-payout",
                "reference": "Thrilok",
                "amount": 40_000,
                "category": "commission",
                "date": "2026-06-30",
            }
        ],
        salaries=SALARY,
    )

    carry = candidate_store._carry_forward_balances("2026-07")["thrilok"]

    assert carry["prior_months"] == ["2026-03", "2026-06"]


def test_recoveries_count_as_a_contributing_month(monkeypatch, tmp_path):
    _arrange(
        monkeypatch,
        tmp_path,
        rows=[_row("june", "2026-06-15")],
        expenses=[],
        salaries=SALARY,
        ledger=[
            {
                "referrer": "Thrilok",
                "amount": 5_000,
                "payment_date": "2026-02-11",
            }
        ],
    )

    carry = candidate_store._carry_forward_balances("2026-07")["thrilok"]

    assert "2026-02" in carry["prior_months"]
    assert carry["prior_recoveries"] == 5_000
    assert (
        carry["prior_owed"] - carry["prior_paid"] - carry["prior_recoveries"]
        == carry["prior_balance"]
    )


def test_settled_months_are_not_named_as_a_source(monkeypatch, tmp_path):
    """April and May 2026 are treated as settled and must not be cited."""
    _arrange(
        monkeypatch,
        tmp_path,
        rows=[_row("april", "2026-04-15"), _row("june", "2026-06-15")],
        expenses=[
            {
                "id": "may-payout",
                "reference": "Thrilok",
                "amount": 10_000,
                "category": "commission",
                "date": "2026-05-30",
            }
        ],
        salaries=SALARY,
    )

    carry = candidate_store._carry_forward_balances("2026-07")["thrilok"]

    assert "2026-04" not in carry["prior_months"]
    assert "2026-05" not in carry["prior_months"]
    assert carry["prior_months"] == ["2026-06"]


def test_zero_movements_do_not_name_a_month(monkeypatch, tmp_path):
    """A payout of 0 is not a reason for a balance, so it must not be cited."""
    _arrange(
        monkeypatch,
        tmp_path,
        rows=[_row("june", "2026-06-15")],
        expenses=[
            {
                "id": "empty",
                "reference": "Thrilok",
                "amount": 0,
                "category": "commission",
                "date": "2026-01-05",
            }
        ],
        salaries=SALARY,
    )

    carry = candidate_store._carry_forward_balances("2026-07")["thrilok"]

    assert "2026-01" not in carry["prior_months"]


def test_reports_the_closure_complimentary_inside_a_carried_balance(
    monkeypatch, tmp_path
):
    """A profile closure grants the closure admin a complimentary amount.

    That grant can come from another handler's candidate, so a balance made of
    it must be reported as complimentary rather than as ordinary arrears.
    """
    closure_row = _row("closure", "2026-06-20")
    closure_row["reference"] = "Pavan Kalyan"
    closure_row["stage"] = "completed"

    _arrange(
        monkeypatch,
        tmp_path,
        rows=[closure_row],
        expenses=[],
        salaries={},
    )
    monkeypatch.setattr(
        candidate_store, "admin_complimentary_amount", lambda _r: 5_000
    )
    monkeypatch.setattr(
        candidate_store, "referrer_complimentary_amount", lambda _r: 0
    )
    monkeypatch.setattr(
        candidate_store,
        "handler_earning_allocations",
        lambda _r: {"pavan kalyan": 16_000, "thrilok": 5_000},
    )

    carry = candidate_store._carry_forward_balances("2026-07")["thrilok"]

    assert carry["prior_complimentary"] == 5_000
    assert carry["prior_complimentary_count"] == 1
    assert carry["prior_balance"] == 5_000
    # Complimentary is part of the commission figure, never added on top of it.
    assert carry["prior_complimentary"] <= carry["prior_commission"]
    assert (
        carry["prior_owed"] - carry["prior_paid"] - carry["prior_recoveries"]
        == carry["prior_balance"]
    )


def test_no_complimentary_reported_when_none_was_granted(monkeypatch, tmp_path):
    _arrange(
        monkeypatch,
        tmp_path,
        rows=[_row("june", "2026-06-15")],
        expenses=[],
        salaries=SALARY,
    )
    monkeypatch.setattr(
        candidate_store, "admin_complimentary_amount", lambda _r: 0
    )
    monkeypatch.setattr(
        candidate_store, "referrer_complimentary_amount", lambda _r: 0
    )

    carry = candidate_store._carry_forward_balances("2026-07")["thrilok"]

    assert carry["prior_complimentary"] == 0
    assert carry["prior_complimentary_count"] == 0


def test_referrer_complimentary_is_credited_to_the_referrer(monkeypatch, tmp_path):
    _arrange(
        monkeypatch,
        tmp_path,
        rows=[_row("june", "2026-06-15")],
        expenses=[],
        salaries={},
    )
    monkeypatch.setattr(
        candidate_store, "admin_complimentary_amount", lambda _r: 0
    )
    monkeypatch.setattr(
        candidate_store, "referrer_complimentary_amount", lambda _r: 2_000
    )

    carry = candidate_store._carry_forward_balances("2026-07")["thrilok"]

    assert carry["prior_complimentary"] == 2_000
    assert carry["prior_complimentary_count"] == 1
