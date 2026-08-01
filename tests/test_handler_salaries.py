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


def test_completed_profile_extras_are_additive_and_allocated_separately(monkeypatch, tmp_path):
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
    rows = [
        {
            "id": "charan-profile",
            "name": "Charan Candidate",
            "reference": "Charan",
            "payment": 20_000,
            "expected_payment": 20_000,
            "service_type": "profile_service",
            "logged_date": "2026-07-15",
            "date": "2026-07-15",
            "stage": "completed",
        },
        {
            "id": "thrilok-profile",
            "name": "Thrilok Candidate",
            "reference": "Thrilok",
            "payment": 20_000,
            "expected_payment": 20_000,
            "service_type": "profile_service",
            "logged_date": "2026-07-16",
            "date": "2026-07-16",
            "stage": "completed",
        },
    ]

    def fake_list_candidates(**kwargs):
        selected = list(rows)
        reference = kwargs.get("reference")
        if reference and str(reference).lower() != "all":
            selected = [
                row for row in selected
                if row["reference"].lower() == str(reference).lower()
            ]
        service_type = kwargs.get("service_type")
        if service_type and service_type != "all":
            selected = [row for row in selected if row["service_type"] == service_type]
        return selected

    monkeypatch.setattr(candidate_store, "list_candidates", fake_list_candidates)
    monkeypatch.setattr(candidate_store, "_load", lambda **_kwargs: {"candidates": rows})
    monkeypatch.setattr(candidate_store, "_carry_forward_balances", lambda **_kwargs: {})
    monkeypatch.setattr(payment_verification_engine, "recovery_summary_by_referrer", lambda **_kwargs: {})

    result = candidate_store.stats(month="2026-07", _skip_pending_works=True)
    performers = {item["ref_key"]: item for item in result["top_performers"]}

    charan = performers["charan"]
    assert charan["base_commission_total"] == 10_000
    assert charan["referrer_complimentary_total"] == 5_000
    assert charan["admin_complimentary_total"] == 0
    assert charan["commission_total"] == 15_000

    thrilok = performers["thrilok"]
    assert thrilok["base_commission_total"] == 10_000
    assert thrilok["referrer_complimentary_total"] == 5_000
    assert thrilok["admin_complimentary_total"] == 10_000
    assert thrilok["commission_total"] == 25_000
    assert thrilok["salary_total"] == 15_000
    assert thrilok["auto_earnings_total"] == 40_000

    assert result["handler_base_commission_total"] == 20_000
    assert result["handler_referrer_complimentary_total"] == 10_000
    assert result["handler_admin_complimentary_total"] == 10_000
    assert result["handler_commission_total"] == 40_000

    scoped = candidate_store.stats(
        month="2026-07",
        reference="Thrilok",
        _skip_pending_works=True,
    )
    scoped_thrilok = scoped["top_performers"][0]
    assert scoped["total"] == 1
    assert scoped_thrilok["count"] == 1
    assert scoped_thrilok["admin_complimentary_count"] == 2
    assert scoped_thrilok["commission_total"] == 25_000


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


def test_carry_forward_allocates_completed_profile_extras(monkeypatch, tmp_path):
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
    june_row = {
        "id": "june-closed-profile",
        "name": "Candidate",
        "reference": "Charan",
        "payment": 20_000,
        "expected_payment": 20_000,
        "service_type": "profile_service",
        "logged_date": "2026-06-15",
        "date": "2026-06-15",
        "stage": "completed",
    }
    monkeypatch.setattr(candidate_store, "_load", lambda **_kwargs: {"candidates": [june_row]})
    monkeypatch.setattr(candidate_store, "_stats_rows_deduped", lambda rows: rows)
    monkeypatch.setattr(payment_verification_engine, "ledger_entries", lambda **_kwargs: [])

    carry = candidate_store._carry_forward_balances("2026-07")

    assert carry["charan"]["prior_commission"] == 15_000
    assert carry["charan"]["prior_balance"] == 15_000
    assert carry["thrilok"]["prior_commission"] == 5_000
    assert carry["thrilok"]["prior_salary"] == 15_000
    assert carry["thrilok"]["prior_balance"] == 20_000
