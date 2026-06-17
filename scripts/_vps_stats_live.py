"""Run candidate stats on VPS using venv + Postgres."""
from __future__ import annotations

import json
import os
import sys
import tempfile

import paramiko

HOST, USER, REMOTE = "187.127.169.159", "root", "/opt/telegramforward"
PASSWORD = os.environ.get("VPS_PASSWORD", "")

PROBE = """
import json, sys, os
os.chdir("/opt/telegramforward")
sys.path.insert(0, "/opt/telegramforward")
from core.db.connection import use_postgres
from features.candidate_store import list_candidates, stats
print("use_postgres", use_postgres())
rows = list_candidates()
s = stats(month="2026-06")
out = {
    "rows": len(rows),
    "revenue_total": s.get("revenue_total"),
    "revenue_completed": s.get("revenue_completed"),
    "expected_total": s.get("expected_total"),
    "pending_total": s.get("pending_total"),
    "total": s.get("total"),
    "handler_commission_total": s.get("handler_commission_total"),
    "handler_auto_earnings_total": s.get("handler_auto_earnings_total"),
    "handler_paid_out_total": s.get("handler_paid_out_total"),
    "net_handler_payout": s.get("net_handler_payout"),
    "top_performers": [
        {
            "name": p.get("name"),
            "revenue_total": p.get("revenue_total"),
            "commission_total": p.get("commission_total"),
            "salary_total": p.get("salary_total"),
            "net_payable": p.get("net_payable"),
        }
        for p in (s.get("top_performers") or [])[:5]
    ],
}
print("RESULT", json.dumps(out))
"""


def main() -> int:
    if not PASSWORD:
        print("VPS_PASSWORD not set", file=sys.stderr)
        return 1
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(HOST, username=USER, password=PASSWORD, timeout=30)
    sftp = client.open_sftp()
    remote = f"{REMOTE}/scripts/_stats_probe_tmp.py"
    with sftp.file(remote, "w") as f:
        f.write(PROBE)
    sftp.close()
    _, stdout, stderr = client.exec_command(
        f"{REMOTE}/venv/bin/python {remote}", timeout=90
    )
    out = stdout.read().decode()
    err = stderr.read().decode()
    print(out)
    if err.strip():
        print(err, file=sys.stderr)
    for line in out.splitlines():
        if line.startswith("RESULT "):
            data = json.loads(line.split("RESULT ", 1)[1])
            print("\n=== June 2026 (Postgres / live) ===")
            print(f"Total revenue (received):  ₹{data['revenue_total']:,}")
            print(f"From completed:            ₹{data['revenue_completed']:,}")
            print(f"Pending collections:       ₹{data['pending_total']:,}")
            print(f"Candidates:                {data['total']}")
            print(f"Handler commission owed:   ₹{data.get('handler_commission_total', 0):,}")
            print(f"Total handler payouts due: ₹{data.get('handler_auto_earnings_total', 0):,}")
            break
    client.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
