"""Report which transactions are recorded in more than one place.

Read-only. Run it on the host that owns the data, before any correction:

    python scripts/reconciliation_report.py
    python scripts/reconciliation_report.py --json > reconciliation.json

Nothing is modified. Correcting a finding is a separate, deliberate step, so
the numbers can be reviewed and the totals checked first.
"""
from __future__ import annotations

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from features import financial_reconciliation  # noqa: E402


def _render(report: dict) -> str:
    lines = [
        "=" * 72,
        "FINANCIAL RECONCILIATION - REPORT ONLY, NOTHING CHANGED",
        "=" * 72,
        f"records scanned        : {report['scanned']}",
    ]
    for name, status in report["sources"].items():
        lines.append(f"  {name:<20}: {status}")
    lines += [
        f"duplicate groups       : {report['duplicate_groups']}",
        f"  auto-correctable     : {len(report['confirmed'])}"
        f"  (Rs {report['confirmed_financial_impact']:,})",
        f"  needs manual review  : {len(report['requires_review'])}",
        f"total financial impact : Rs {report['total_financial_impact']:,}",
    ]
    if not report["groups"]:
        lines.append("\nNo transaction is recorded more than once.")
        return "\n".join(lines)

    lines.append("\nby handler:")
    for bucket in report["by_handler"]:
        lines.append(
            f"  {bucket['handler']:<28} {bucket['groups']} group(s)"
            f"  Rs {bucket['impact']:,}"
        )

    def _detail(groups: list, heading: str) -> None:
        if not groups:
            return
        lines.append(f"\n{heading}")
        for group in groups:
            keep = group["canonical"]
            lines.append(
                f"\n  [matched on {group['basis']}] {group['handler']}"
                f" - Rs {group['amount']:,} ({group['month']})"
            )
            lines.append(
                f"    keep      {keep['kind']:<16} {keep['record_id']}"
                f"  {keep.get('source_module')}  {keep.get('date')}"
            )
            for dup in group["duplicates"]:
                note = str(dup.get("note") or "")[:40]
                lines.append(
                    f"    duplicate {dup['kind']:<16} {dup['record_id']}"
                    f"  {dup.get('source_module')}  {dup.get('date')}  {note!r}"
                )

    _detail(report["confirmed"], "CONFIRMED - safe to correct automatically:")
    _detail(
        report["requires_review"],
        "REQUIRES MANUAL REVIEW - not corrected, evidence is not conclusive:",
    )
    lines.append(
        "\nTo correct a finding, void the duplicate — it keeps the row and its"
        "\nproof and only stops it counting as money paid:"
        "\n  POST /handler-expenses/<id>/void"
        '\n       {"status": "RECLASSIFIED_TO_RECOVERY", "reason": "...",'
        ' "ledger_ref": "<kept record_id>"}'
    )
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true", help="emit the raw report")
    args = parser.parse_args()

    report = financial_reconciliation.reconciliation_report()
    if args.json:
        print(json.dumps(report, indent=2, ensure_ascii=False, default=str))
    else:
        print(_render(report))
    # Non-zero when something needs a decision, so a scheduled run can alert.
    return 1 if report["duplicate_groups"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
