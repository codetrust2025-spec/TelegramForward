"""Cross-module view of every record that moves money, and what double-counts.

Each financial module stores its own rows in its own shape. Nothing compares
them, so one bank transaction can be recorded in two modules and deducted
twice — a candidate's payment into a referrer's own account is posted
automatically as a recovery, and the same screenshot is then filed by hand as a
handler expense.

`collect_transactions` flattens every store into one comparable shape;
`reconciliation_report` groups them by transaction identity and reports what
overlaps. Both are read-only. Correcting a duplicate is a separate, explicit
step (`features.handler_expenses.void_expense`) so a report can be reviewed
before anything changes.

Handler salaries are deliberately not included: a salary is an accrued monthly
entitlement, not a bank transaction, so it has no counterpart to duplicate.
"""

from __future__ import annotations

from typing import Any, Iterable

from features import transaction_identity

# What each ledger transaction_type does to a handler's balance.
#
# Only two of these move it. A COMMISSION_PAYOUT or an expense reimbursement is
# the ledger's own record of a handler expense that `handler_expenses` already
# holds — the balance is computed from the expense store, so counting the
# ledger row as well would report every legitimate payout as a duplicate of
# itself. They are mirrors, not second effects.
_LEDGER_KINDS = {
    "CANDIDATE_FEE_RECEIVED_BY_COMPANY": "candidate_payment",
    # One entry, two facts: the candidate paid, and the referrer now holds
    # money the company must recover from their commission.
    "CANDIDATE_FEE_RECEIVED_BY_REFERRER": "recovery",
    "COMMISSION_PAYOUT": "ledger_mirror",
    "APPROVED_EXPENSE_REIMBURSEMENT": "ledger_mirror",
    "RECOVERABLE_ADVANCE": "adjustment",
}


def _canonical(name: Any) -> str:
    """One person, one name.

    The same handler is written several ways across modules ("Pavan Kalyan",
    "Lukka Pavan Kalyan"), and a transaction recorded against two spellings
    would otherwise look like two transactions.
    """
    text = str(name or "").strip()
    if not text:
        return ""
    try:
        from features import candidate_store

        return candidate_store._reference_key(text)
    except Exception:
        return text.lower()


def canonical_transaction(tx: dict[str, Any]) -> dict[str, Any]:
    """Resolve a transaction's party names before it is compared to others."""
    return {**tx, "receiver": _canonical(tx.get("receiver"))}


def _ledger_transactions() -> list[dict[str, Any]]:
    from features import payment_verification_engine

    rows: list[dict[str, Any]] = []
    for entry in payment_verification_engine.ledger_entries():
        kind = _LEDGER_KINDS.get(str(entry.get("transaction_type") or "").upper())
        if not kind:
            continue
        rows.append(
            {
                "record_id": entry.get("ledger_entry_id") or entry.get("id"),
                "kind": kind,
                "source_module": entry.get("source_module") or "payment_ledger",
                "amount": entry.get("total_payout_adjustment") or entry.get("amount"),
                "date": entry.get("payment_date") or entry.get("effective_date"),
                "payer": entry.get("payer") or entry.get("sender_name"),
                "receiver": _canonical(
                    entry.get("receiver")
                    or entry.get("receiver_registry_name")
                    or entry.get("referrer")
                ),
                "handler": entry.get("referrer") or entry.get("receiver_registry_name"),
                "external_transaction_id": entry.get("external_transaction_id"),
                "screenshot_hash": entry.get("screenshot_hash"),
                # A reversed or pending entry is not currently moving money.
                "voided": str(entry.get("status") or "").lower() != "posted",
                "created_at": entry.get("created_at"),
                "linked_candidate_id": entry.get("candidate_id"),
                "note": entry.get("purpose"),
            }
        )
    return rows


def _handler_expense_transactions(*, exclude_id: str = "") -> list[dict[str, Any]]:
    from features import handler_expenses

    return [
        {**tx, "receiver": _canonical(tx.get("receiver"))}
        for tx in (
            handler_expenses.as_transaction(row)
            for row in handler_expenses.list_expenses(include_voided=True)
            if row.get("id") != exclude_id
        )
    ]


def _company_expense_transactions() -> list[dict[str, Any]]:
    from features import company_expenses

    return [
        {
            "record_id": row.get("id"),
            "kind": "expense",
            "source_module": "company_expenses",
            "amount": row.get("amount"),
            "date": row.get("date"),
            "payer": "company",
            "receiver": row.get("vendor") or row.get("payee") or row.get("category"),
            "handler": "",
            "external_transaction_id": row.get("external_transaction_id"),
            "screenshot_hash": row.get("screenshot_hash"),
            "voided": False,
            "created_at": row.get("created_at"),
            "note": row.get("note"),
        }
        for row in company_expenses.list_expenses()
    ]


def collect_transactions(*, exclude_expense_id: str = "") -> list[dict[str, Any]]:
    """Every money-moving record across every module, in one shape.

    A store that cannot be read is skipped rather than failing the scan: a
    partial report is more useful than none, and the caller can see which
    sources were unavailable via `reconciliation_report`.
    """
    rows: list[dict[str, Any]] = []
    for source in (
        lambda: _ledger_transactions(),
        lambda: _handler_expense_transactions(exclude_id=exclude_expense_id),
        lambda: _company_expense_transactions(),
    ):
        try:
            rows.extend(source())
        except Exception:
            continue
    return rows


def source_status() -> dict[str, str]:
    """Which stores the scan could read. Reported alongside any findings."""
    status: dict[str, str] = {}
    for name, source in (
        ("payment_ledger", _ledger_transactions),
        ("handler_expenses", _handler_expense_transactions),
        ("company_expenses", _company_expense_transactions),
    ):
        try:
            status[name] = f"ok ({len(source())} records)"
        except Exception as exc:
            status[name] = f"unavailable: {type(exc).__name__}"
    return status


def reconciliation_report(
    records: Iterable[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Read-only summary of transactions recorded more than once.

    Nothing is modified. `groups` names, for each duplicated transaction, the
    record to keep and the ones that double-count it, so a reviewer can decide
    before any correction is applied.
    """
    rows = list(records) if records is not None else collect_transactions()
    groups = transaction_identity.find_duplicates(rows)
    by_handler: dict[str, dict[str, Any]] = {}
    for group in groups:
        key = str(group.get("handler") or "unattributed").strip().lower()
        bucket = by_handler.setdefault(
            key,
            {"handler": group.get("handler") or "unattributed", "groups": 0, "impact": 0},
        )
        bucket["groups"] += 1
        bucket["impact"] += int(group.get("financial_impact") or 0)
    return {
        "scanned": len(rows),
        "sources": source_status(),
        "duplicate_groups": len(groups),
        "total_financial_impact": sum(
            int(g.get("financial_impact") or 0) for g in groups
        ),
        "by_handler": sorted(
            by_handler.values(), key=lambda b: b["impact"], reverse=True
        ),
        "groups": groups,
        # Nothing here has been applied; correction is a separate action.
        "mode": "report_only",
    }
