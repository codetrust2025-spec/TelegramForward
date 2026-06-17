#!/usr/bin/env python3
"""Restore handler payout ledger (May/June only) wiped by prune bug."""
from __future__ import annotations
import os, socket, sys, json
import paramiko

HOST, USER = "187.127.169.159", "root"
PWD = os.environ.get("VPS_PASSWORD", "")

BACKUP = "/opt/telegramforward.old/backups/pre_prune_20260605_093849/handler_expenses.json"
TARGET = "/opt/telegramforward.old/data/handler_expenses.json"
KEEP_MONTHS = ("2026-05", "2026-06")

def ssh_run(script: str) -> str:
    sock = socket.create_connection((HOST, 22), timeout=30)
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(hostname=HOST, username=USER, password=PWD, sock=sock)
    cmd = f"cd /opt/telegramforward.old && source venv/bin/activate && python3 << 'PYEOF'\n{script}\nPYEOF"
    _, o, e = c.exec_command(cmd, timeout=120)
    out = o.read().decode("utf-8", errors="replace")
    err = e.read().decode("utf-8", errors="replace")
    c.close()
    return out + ("\nSTDERR: " + err if err.strip() else "")

RESTORE = f'''
import json, shutil
from datetime import datetime, timezone

BACKUP = "{BACKUP}"
TARGET = "{TARGET}"
KEEP = {KEEP_MONTHS}

shutil.copy2(TARGET, TARGET + ".empty_bak")

with open(BACKUP) as f:
    data = json.load(f)

kept = []
for row in data.get("expenses", []):
    d = (row.get("date") or "")[:7]
    if d in KEEP:
        kept.append(row)

out = {{"expenses": kept, "updated_at": datetime.now(timezone.utc).isoformat()}}
with open(TARGET, "w") as f:
    json.dump(out, f, indent=2)

print(f"restored {{len(kept)}} payout rows (May/June)")
for row in kept:
    print(f"  {{row['date']}} {{row['reference']}} ₹{{row['amount']}} {{row.get('note','')}}")

from features.candidate_store import stats
s = stats(month="2026-06")
thr = next(p for p in s["top_performers"] if p["name"].lower() == "thrilok")
print("\\nThrilok JUN after restore:")
print(f"  owed (salary+comm): ₹{{thr['auto_earnings_total']}}")
print(f"  paid out: ₹{{thr['paid_out_total']}}")
print(f"  net still owe: ₹{{thr['net_payable']}}")
print(f"\\nFleet JUN net_handler_payout: ₹{{s['net_handler_payout']}}")
'''

if __name__ == "__main__":
    if not PWD:
        sys.exit("Set VPS_PASSWORD")
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    print(ssh_run(RESTORE))
