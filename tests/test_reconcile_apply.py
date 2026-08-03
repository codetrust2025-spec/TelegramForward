"""Applying a correction moves exactly the balance it claims to, or nothing."""
from __future__ import annotations

import importlib
import sys

import pytest


@pytest.fixture()
def apply_module(tmp_path, monkeypatch):
    from features import handler_expenses

    monkeypatch.setattr(handler_expenses, "_FILE", str(tmp_path / "handler_expenses.json"))
    monkeypatch.setattr(handler_expenses, "PROOFS_DIR", str(tmp_path / "proofs"))

    from features import financial_reconciliation

    monkeypatch.setattr(financial_reconciliation, "_ledger_transactions", lambda: [])
    monkeypatch.setattr(financial_reconciliation, "_company_expense_transactions", lambda: [])
    monkeypatch.setattr(
        financial_reconciliation, "_canonical", lambda n: str(n or "").strip().lower()
    )

    sys.path.insert(0, str(importlib.import_module("features").__path__[0] + "/../scripts"))
    module = importlib.import_module("reconcile_apply")
    return importlib.reload(module), handler_expenses


def test_a_void_is_validated_against_the_expense_own_handler_spelling(
    apply_module, monkeypatch, capsys
):
    """The finding is named after the record being kept, whose spelling of the
    handler can differ from the expense's. Validating on the finding's name
    would roll back a correction that in fact reconciled."""
    reconcile_apply, handler_expenses = apply_module
    row = handler_expenses.create_expense(
        {"reference": "Pavan Kalyan", "amount": 5000, "date": "2026-07-28",
         "category": "commission", "note": "expenses emergency"}
    )
    monkeypatch.setattr(
        reconcile_apply.financial_reconciliation,
        "reconciliation_report",
        lambda: {
            "confirmed": [
                {
                    "basis": "payment_id",
                    # Alias spelling, deliberately unlike the expense's.
                    "handler": "LUKKA PAVAN KALYAN",
                    "canonical": {"record_id": "le_200d", "kind": "recovery"},
                    "duplicates": [
                        {
                            "record_id": row["id"],
                            "source_module": "handler_expenses",
                            "amount": 5000,
                        }
                    ],
                }
            ],
            "requires_review": [],
        },
    )
    monkeypatch.setattr(sys, "argv", ["reconcile_apply", "--apply", "--actor", "admin"])

    assert reconcile_apply.main() == 0
    assert "ROLLED BACK" not in capsys.readouterr().out

    stored = handler_expenses.list_expenses(include_voided=True)[0]
    assert stored["void_status"] == "RECLASSIFIED_TO_RECOVERY"
    assert stored["voided_ledger_ref"] == "le_200d"
    assert stored["voided_by"] == "admin"
    assert stored["note"] == "expenses emergency"       # history preserved
    assert handler_expenses.total_for_handler("Pavan Kalyan") == 0


def test_an_unexpected_balance_move_rolls_the_whole_correction_back(
    apply_module, monkeypatch, capsys
):
    reconcile_apply, handler_expenses = apply_module
    row = handler_expenses.create_expense(
        {"reference": "Pavan Kalyan", "amount": 5000, "date": "2026-07-28",
         "category": "commission"}
    )
    handler_expenses.create_expense(
        {"reference": "Thrilok", "amount": 1000, "date": "2026-07-28", "category": "food"}
    )
    monkeypatch.setattr(
        reconcile_apply.financial_reconciliation,
        "reconciliation_report",
        lambda: {
            "confirmed": [
                {
                    "basis": "payment_id",
                    "handler": "Pavan Kalyan",
                    "canonical": {"record_id": "le_200d", "kind": "recovery"},
                    "duplicates": [
                        {"record_id": row["id"], "source_module": "handler_expenses",
                         "amount": 5000}
                    ],
                }
            ],
            "requires_review": [],
        },
    )

    # An unrelated handler's total shifting mid-correction must abort everything.
    real_summary = handler_expenses.summary_by_handler
    calls = {"n": 0}

    def _drifting_summary(*args, **kwargs):
        result = real_summary(*args, **kwargs)
        calls["n"] += 1
        if calls["n"] > 1 and "thrilok" in result:
            result["thrilok"]["total"] += 700
        return result

    monkeypatch.setattr(handler_expenses, "summary_by_handler", _drifting_summary)
    monkeypatch.setattr(sys, "argv", ["reconcile_apply", "--apply", "--actor", "admin"])

    assert reconcile_apply.main() == 1
    assert "ROLLED BACK" in capsys.readouterr().err
    # The store was restored: the expense still counts as money paid.
    assert handler_expenses.total_for_handler("Pavan Kalyan") == 5000


def test_apply_refuses_without_an_actor(apply_module, monkeypatch):
    reconcile_apply, _ = apply_module
    monkeypatch.setattr(sys, "argv", ["reconcile_apply", "--apply"])
    assert reconcile_apply.main() == 2


def test_a_dry_run_writes_nothing(apply_module, monkeypatch, capsys):
    reconcile_apply, handler_expenses = apply_module
    row = handler_expenses.create_expense(
        {"reference": "Pavan Kalyan", "amount": 5000, "date": "2026-07-28",
         "category": "commission"}
    )
    monkeypatch.setattr(
        reconcile_apply.financial_reconciliation,
        "reconciliation_report",
        lambda: {
            "confirmed": [
                {
                    "basis": "payment_id",
                    "handler": "Pavan Kalyan",
                    "canonical": {"record_id": "le_200d", "kind": "recovery"},
                    "duplicates": [
                        {"record_id": row["id"], "source_module": "handler_expenses",
                         "amount": 5000}
                    ],
                }
            ],
            "requires_review": [],
        },
    )
    monkeypatch.setattr(sys, "argv", ["reconcile_apply", "--dry-run"])
    assert reconcile_apply.main() == 0
    assert "nothing was written" in capsys.readouterr().out
    assert handler_expenses.total_for_handler("Pavan Kalyan") == 5000
