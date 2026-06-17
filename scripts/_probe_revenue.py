"""Fetch company revenue from production VPS candidate backups."""
from __future__ import annotations

import json
import os
import sys
import tempfile

import paramiko

HOST, USER, REMOTE = "187.127.169.159", "root", "/opt/telegramforward"
PASSWORD = os.environ.get("VPS_PASSWORD", "")

CANDIDATE_FILES = [
    f"{REMOTE}/data/candidates.json",
    f"{REMOTE}/data/candidates.json.pre_pg_backup_20260528_082739",
    "/opt/telegramforward.old/backups/pre_update_20260611_134335/data/candidates.json",
    "/opt/telegramforward.old/backups/pre_prune_20260605_093849/candidates.json",
]


def sftp_get(remote_path: str) -> str | None:
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(HOST, username=USER, password=PASSWORD, timeout=30)
    sftp = client.open_sftp()
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".json") as tmp:
            local = tmp.name
        sftp.get(remote_path, local)
        sftp.close()
        client.close()
        return local
    except OSError:
        sftp.close()
        client.close()
        return None


def summarize(path: str, month: str) -> dict | None:
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError):
        return None
    rows = data.get("candidates") or []
    if not rows:
        return None
    month_rows = [r for r in rows if (r.get("date") or "")[:7] == month]
    rev = sum(int(r.get("payment") or 0) for r in month_rows)
    exp = sum(int(r.get("expected_payment") or 0) for r in month_rows)
    pend = sum(
        max(
            0,
            (int(r.get("expected_payment") or 0) or 0) - int(r.get("payment") or 0),
        )
        for r in month_rows
    )
    completed_rev = sum(
        int(r.get("payment") or 0)
        for r in month_rows
        if (r.get("stage") or "") == "completed"
    )
    return {
        "month_count": len(month_rows),
        "revenue_total": rev,
        "revenue_completed": completed_rev,
        "expected_total": exp,
        "pending_total": pend,
        "all_time_rev": sum(int(r.get("payment") or 0) for r in rows),
        "all_time_count": len(rows),
    }


def main() -> int:
    if not PASSWORD:
        print("VPS_PASSWORD not set", file=sys.stderr)
        return 1

    from datetime import datetime

    month = datetime.now().strftime("%Y-%m")
    month_label = datetime.now().strftime("%B %Y")

    best = None
    best_path = None
    for remote in CANDIDATE_FILES:
        local = sftp_get(remote)
        if not local:
            continue
        stats = summarize(local, month)
        os.unlink(local)
        if stats and stats["all_time_count"] > 0:
            if best is None or stats["all_time_count"] >= best["all_time_count"]:
                best = stats
                best_path = remote

    print(f"Company revenue — {month_label}\n")

    live = sftp_get(f"{REMOTE}/data/candidates.json")
    live_stats = summarize(live, month) if live else None
    if live:
        os.unlink(live)

    if live_stats and live_stats["all_time_count"] > 0:
        s = live_stats
        source = "live dashboard data"
    elif best:
        s = best
        source = f"latest backup ({best_path})"
        print("Note: Live candidates.json is empty on production.")
        print("Figures below are from the most recent backup with records.\n")
    else:
        print("No candidate payment records found on the server.")
        print("Live revenue this month: ₹0")
        return 0

    print(f"Source: {source}\n")
    print(f"Cash received (Total revenue):  ₹{s['revenue_total']:,}")
    print(f"From completed deals:           ₹{s['revenue_completed']:,}")
    print(f"Expected / booked:              ₹{s['expected_total']:,}")
    print(f"Still pending:                  ₹{s['pending_total']:,}")
    print(f"Candidates logged this month:   {s['month_count']}")
    print(f"\nAll-time received:              ₹{s['all_time_rev']:,} ({s['all_time_count']} candidates)")

    if live_stats and live_stats["all_time_count"] == 0 and best:
        print(
            "\n⚠ Live Candidates tracker shows ₹0 — new entries may not be saving "
            "until candidates.json is restored."
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
