"""The cross-module scan flags real double-counting and nothing else."""
from __future__ import annotations

import pytest

from features import financial_reconciliation as fr


@pytest.fixture(autouse=True)
def _no_alias_lookup(monkeypatch):
    monkeypatch.setattr(fr, "_canonical", lambda n: str(n or "").strip().lower())


def _ledger_entry(**over):
    entry = {
        "ledger_entry_id": "le_1",
        "transaction_type": "CANDIDATE_FEE_RECEIVED_BY_REFERRER",
        "status": "posted",
        "source_module": "public_slot_booking",
        "total_payout_adjustment": 5000,
        "payment_date": "2026-07-22",
        "referrer": "Lukka Pavan Kalyan",
        "receiver_registry_name": "Lukka Pavan Kalyan",
        "created_at": "2026-07-22T11:47:00+00:00",
        "candidate_id": "cand_sriram",
    }
    entry.update(over)
    return entry


def _expenses(monkeypatch, rows):
    monkeypatch.setattr(fr, "_handler_expense_transactions", lambda **_: rows)
    monkeypatch.setattr(fr, "_company_expense_transactions", lambda: [])


def _expense(**over):
    row = {
        "record_id": "exp_1",
        "kind": "expense",
        "source_module": "handler_expenses",
        "amount": 5000,
        "date": "2026-07-22",
        "receiver": "lukka pavan kalyan",
        "handler": "Lukka Pavan Kalyan",
        "voided": False,
        "created_at": "2026-07-23T09:00:00+00:00",
    }
    row.update(over)
    return row


def test_a_commission_payout_is_not_a_duplicate_of_the_expense_it_mirrors(monkeypatch):
    # Every handler expense also writes a COMMISSION_PAYOUT ledger row for the
    # same money. Only the expense store feeds the balance, so this is one
    # effect recorded twice for audit, not money deducted twice.
    from features import payment_verification_engine

    monkeypatch.setattr(
        payment_verification_engine,
        "ledger_entries",
        lambda **_: [_ledger_entry(transaction_type="COMMISSION_PAYOUT")],
    )
    _expenses(monkeypatch, [_expense()])
    report = fr.reconciliation_report()
    assert report["duplicate_groups"] == 0


def test_a_recovery_refiled_as_an_expense_is_reported(monkeypatch):
    from features import payment_verification_engine

    monkeypatch.setattr(
        payment_verification_engine, "ledger_entries", lambda **_: [_ledger_entry()]
    )
    _expenses(monkeypatch, [_expense()])
    report = fr.reconciliation_report()
    assert report["duplicate_groups"] == 1
    assert report["total_financial_impact"] == 5000
    group = report["groups"][0]
    assert group["canonical"]["kind"] == "recovery"
    assert [d["record_id"] for d in group["duplicates"]] == ["exp_1"]
    assert group["month"] == "2026-07"


def test_a_reversed_ledger_entry_is_not_counted(monkeypatch):
    from features import payment_verification_engine

    monkeypatch.setattr(
        payment_verification_engine,
        "ledger_entries",
        lambda **_: [_ledger_entry(status="reversed")],
    )
    _expenses(monkeypatch, [_expense()])
    assert fr.reconciliation_report()["duplicate_groups"] == 0


def test_an_already_voided_expense_is_not_reported_again(monkeypatch):
    from features import payment_verification_engine

    monkeypatch.setattr(
        payment_verification_engine, "ledger_entries", lambda **_: [_ledger_entry()]
    )
    _expenses(monkeypatch, [_expense(voided=True)])
    assert fr.reconciliation_report()["duplicate_groups"] == 0


def test_findings_are_grouped_by_handler_with_the_amount_at_stake(monkeypatch):
    from features import payment_verification_engine

    monkeypatch.setattr(
        payment_verification_engine,
        "ledger_entries",
        lambda **_: [
            _ledger_entry(),
            _ledger_entry(
                ledger_entry_id="le_2",
                referrer="Venugopal",
                receiver_registry_name="Venugopal",
                total_payout_adjustment=2000,
                payment_date="2026-07-15",
            ),
        ],
    )
    _expenses(
        monkeypatch,
        [
            _expense(),
            _expense(
                record_id="exp_2", receiver="venugopal", handler="Venugopal",
                amount=2000, date="2026-07-15",
            ),
        ],
    )
    report = fr.reconciliation_report()
    assert report["duplicate_groups"] == 2
    assert report["total_financial_impact"] == 7000
    assert [b["impact"] for b in report["by_handler"]] == [5000, 2000]


def test_an_unreadable_source_does_not_abort_the_scan(monkeypatch):
    from features import payment_verification_engine

    def _boom(**_):
        raise OSError("ledger file missing")

    monkeypatch.setattr(payment_verification_engine, "ledger_entries", _boom)
    _expenses(monkeypatch, [_expense()])
    report = fr.reconciliation_report()
    assert report["scanned"] == 1
    assert report["sources"]["payment_ledger"].startswith("unavailable")
