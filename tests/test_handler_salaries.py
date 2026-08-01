import json

from features import candidate_store, handler_expenses, handler_salaries
from features import payment_verification_engine


def _write_salary_store(tmp_path, salaries):
    path = tmp_path / "handler_salaries.json"
    path.write_text(json.dumps({"salaries": salaries}), encoding="utf-8")
    return str(path)


def test_only_configured_handler_receives_salary_in_active_month(monkeypatch, tmp_path):
    monkeypatch.setattr(
        handler_salaries,
        "_FILE",
        _write_salary_store(
            tmp_path,
            {
                "thrilok": {
                    "reference": "Thrilok",
                    "monthly_salary": 15_000,
                    "active_from": "2026-05",
                    "active_until": None,
                }
            },
        ),
    )

    may = handler_salaries.salary_owed_by_handler("2026-05")
    july = handler_salaries.salary_owed_by_handler("2026-07")

    assert may["thrilok"]["owed"] == 15_000
    assert july["thrilok"]["monthly_salary"] == 15_000
    assert "another handler" not in july
    assert handler_salaries.salary_owed_by_handler("2026-04") == {}


def test_salary_reader_fails_closed_for_invalid_runtime_data(monkeypatch, tmp_path):
    path = tmp_path / "handler_salaries.json"
    path.write_text("not-json", encoding="utf-8")
    monkeypatch.setattr(handler_salaries, "_FILE", str(path))

    assert handler_salaries.salary_owed_by_handler("2026-07") == {}
    assert handler_salaries.salary_owed_by_handler("2026-13") == {}


def test_candidate_stats_add_fixed_salary_to_current_commission(monkeypatch, tmp_path):
    monkeypatch.setattr(
        handler_salaries,
        "_FILE",
        _write_salary_store(
            tmp_path,
            {
                "thrilok": {
                    "reference": "Thrilok",
                    "monthly_salary": 15_000,
                    "active_from": "2026-05",
                }
            },
        ),
    )
    monkeypatch.setattr(handler_expenses, "_FILE", str(tmp_path / "expenses.json"))
    row = {
        "id": "july-candidate",
        "name": "Candidate",
        "reference": "Thrilok",
        "payment": 53_000,
        "logged_date": "2026-07-15",
        "date": "2026-07-15",
        "stage": "in_progress",
    }
    monkeypatch.setattr(candidate_store, "list_candidates", lambda **_kwargs: [row])
    monkeypatch.setattr(candidate_store, "_load", lambda **_kwargs: {"candidates": [row]})
    monkeypatch.setattr(candidate_store, "_carry_forward_balances", lambda **_kwargs: {})
    monkeypatch.setattr(candidate_store, "referrer_commission_amount", lambda _row: 26_500)
    monkeypatch.setattr(payment_verification_engine, "recovery_summary_by_referrer", lambda **_kwargs: {})

    performer = candidate_store.stats(month="2026-07")["top_performers"][0]

    assert performer["commission_total"] == 26_500
    assert performer["salary_total"] == 15_000
    assert performer["auto_earnings_total"] == 41_500
    assert performer["net_payable"] == 41_500


def test_carry_forward_includes_prior_month_salary(monkeypatch, tmp_path):
    monkeypatch.setattr(
        handler_salaries,
        "_FILE",
        _write_salary_store(
            tmp_path,
            {
                "thrilok": {
                    "reference": "Thrilok",
                    "monthly_salary": 15_000,
                    "active_from": "2026-05",
                }
            },
        ),
    )
    expense_path = tmp_path / "handler_expenses.json"
    expense_path.write_text(
        json.dumps(
            {
                "expenses": [
                    {
                        "id": "june-payout",
                        "reference": "Thrilok",
                        "amount": 45_000,
                        "category": "commission",
                        "date": "2026-06-30",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(handler_expenses, "_FILE", str(expense_path))
    june_row = {
        "id": "june-candidate",
        "name": "Candidate",
        "reference": "Thrilok",
        "payment": 60_000,
        "logged_date": "2026-06-15",
        "date": "2026-06-15",
        "stage": "in_progress",
    }
    monkeypatch.setattr(candidate_store, "_load", lambda **_kwargs: {"candidates": [june_row]})
    monkeypatch.setattr(candidate_store, "_stats_rows_deduped", lambda rows: rows)
    monkeypatch.setattr(candidate_store, "referrer_commission_amount", lambda _row: 30_000)
    monkeypatch.setattr(payment_verification_engine, "ledger_entries", lambda **_kwargs: [])

    carry = candidate_store._carry_forward_balances("2026-07")["thrilok"]

    assert carry["prior_commission"] == 30_000
    assert carry["prior_salary"] == 15_000
    assert carry["prior_paid"] == 45_000
    assert carry["prior_balance"] == 0
