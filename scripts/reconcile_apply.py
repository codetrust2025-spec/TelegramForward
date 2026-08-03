"""Void the duplicates the reconciliation report is confident about.

Only groups the report marks `high` confidence are touched: an engine-assigned
payment or a bank reference, with amounts that agree. Everything else is left
alone and stays in the manual-review list — a same-amount, same-day match is
not proof that money moved twice.

Nothing is deleted. A duplicate keeps its row, its proof and its timestamps and
stops counting as money paid.

    python scripts/reconcile_apply.py --dry-run
    python scripts/reconcile_apply.py --apply --actor "<who authorised this>"

The store is copied before any write. Balances are recomputed afterwards and
compared against the expected movement; if they disagree, the copy is restored
and nothing changes.
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from features import financial_reconciliation, handler_expenses  # noqa: E402


def _balances() -> dict[str, int]:
    """Money paid out per handler, which is what voiding a duplicate moves."""
    return {
        key: int(bucket.get("total") or 0)
        for key, bucket in handler_expenses.summary_by_handler().items()
    }


def _void_targets(report: dict) -> list[dict]:
    """Only handler expenses can be voided; other record types need their own
    module to grow a void path, and none are implicated today."""
    targets = []
    for group in report["confirmed"]:
        for duplicate in group["duplicates"]:
            if duplicate.get("source_module") != "handler_expenses":
                print(
                    f"  SKIP {duplicate.get('record_id')}: "
                    f"{duplicate.get('source_module')} has no void path",
                    file=sys.stderr,
                )
                continue
            targets.append(
                {
                    "expense_id": duplicate["record_id"],
                    "amount": int(duplicate.get("amount") or 0),
                    "handler": group.get("handler"),
                    "canonical_id": group["canonical"]["record_id"],
                    "canonical_kind": group["canonical"]["kind"],
                    "basis": group["basis"],
                }
            )
    return targets


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="write the corrections")
    parser.add_argument("--dry-run", action="store_true", help="show what would change")
    parser.add_argument("--actor", default="", help="who authorised this correction")
    args = parser.parse_args()

    if args.apply == args.dry_run:
        print("Choose exactly one of --apply or --dry-run", file=sys.stderr)
        return 2
    if args.apply and not args.actor.strip():
        print("--apply needs --actor: the audit trail records who decided this",
              file=sys.stderr)
        return 2

    report = financial_reconciliation.reconciliation_report()
    targets = _void_targets(report)
    before = _balances()

    print(f"confirmed duplicate groups : {len(report['confirmed'])}")
    print(f"records to void            : {len(targets)}")
    print(f"left for manual review     : {len(report['requires_review'])}")
    for target in targets:
        print(
            f"  void expense {target['expense_id']} (Rs {target['amount']:,},"
            f" {target['handler']}) -> keep {target['canonical_kind']}"
            f" {target['canonical_id']} [matched on {target['basis']}]"
        )
    if not targets:
        print("Nothing to correct.")
        return 0
    if args.dry_run:
        print("\nDry run: nothing was written.")
        return 0

    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    backup = f"{handler_expenses._FILE}.pre-reconcile-{stamp}"
    shutil.copy2(handler_expenses._FILE, backup)
    print(f"\nstore copied to {backup}")

    applied = []
    try:
        for target in targets:
            row = handler_expenses.void_expense(
                target["expense_id"],
                status="RECLASSIFIED_TO_RECOVERY"
                if target["canonical_kind"] == "recovery"
                else "VOIDED_DUPLICATE",
                reason=(
                    f"Same transaction as {target['canonical_kind']} "
                    f"{target['canonical_id']} (matched on {target['basis']}). "
                    f"Money must affect the balance once."
                ),
                actor=args.actor.strip(),
                ledger_ref=str(target["canonical_id"]),
            )
            if row is None:
                raise RuntimeError(f"expense {target['expense_id']} not found")
            applied.append(row)

        # Expected movement, derived from the rows actually voided rather than
        # from the finding's handler name: a group is named after the record
        # being kept, whose spelling of the handler can differ from the
        # expense's own, and the balance is keyed on the expense's spelling.
        expected = dict(before)
        for row in applied:
            key = str(row.get("reference") or "").strip().lower()
            expected[key] = expected.get(key, 0) - int(row.get("amount") or 0)

        after = _balances()
        drift = {
            key: (expected.get(key, 0), after.get(key, 0))
            for key in set(expected) | set(after)
            if expected.get(key, 0) != after.get(key, 0)
        }
        if drift:
            raise RuntimeError(f"balances did not reconcile: {drift}")
    except Exception as exc:
        shutil.copy2(backup, handler_expenses._FILE)
        print(f"\nROLLED BACK - {exc}", file=sys.stderr)
        return 1

    print(f"\nvoided {len(applied)} record(s); balances reconcile")
    for key in sorted(set(before) | set(after)):
        if before.get(key, 0) != after.get(key, 0):
            print(f"  {key:<28} Rs {before.get(key, 0):,} -> Rs {after.get(key, 0):,}")
    print(json.dumps(
        {
            "voided": [
                {
                    "expense_id": r["id"], "amount": r["amount"],
                    "handler": r["reference"], "void_status": r["void_status"],
                    "canonical": r.get("voided_ledger_ref"),
                    "voided_at": r.get("voided_at"), "voided_by": r.get("voided_by"),
                }
                for r in applied
            ],
            "backup": backup,
        },
        indent=2,
    ))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
