"""Print Thrilok Jun 2026 earnings breakdown from VPS data."""
from __future__ import annotations

import json
import os
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import paramiko

HOST = "187.127.169.159"
REMOTE = "/opt/telegramforward.old"
PASSWORD = os.environ.get("VPS_PASSWORD", "")


def main() -> int:
    if not PASSWORD:
        print("VPS_PASSWORD not set")
        return 1

    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(HOST, username="root", password=PASSWORD, timeout=30)

    script = r'''
import json
from pathlib import Path
base = Path("/opt/telegramforward.old/data")
month = "2026-06"
HANDLER = "thrilok"

def ref_key(s):
    return (s or "").strip().lower()

cand = json.loads((base / "candidates.json").read_text(encoding="utf-8"))
rows = []
for r in cand.get("candidates", []):
    if ref_key(r.get("reference")) != HANDLER:
        continue
    created = (r.get("created_at") or r.get("updated_at") or "")[:7]
    if month not in created and (r.get("interview_date") or "")[:7] != month:
        # loose: include if payment month field or any date in june
        pass
    rows.append(r)

# filter june by created/updated/interview
june = []
for r in rows:
    dates = [r.get("created_at","")[:7], r.get("updated_at","")[:7], r.get("interview_date","")[:7]]
    if month in dates or True:  # show all thrilok for debug
        june.append(r)

print("=== Thrilok candidates (all) ===")
total_pay = 0
for r in june:
    pay = int(r.get("payment") or 0)
    total_pay += pay
    comm = pay * 50 // 100
    exp = int(r.get("expected_payment") or 20000)
    bal = max(0, exp - pay)
    print(f"  {r.get('name')} | {r.get('stage')} | paid {pay} / {exp} | comm50% {comm} | client due {bal}")

print(f"Total client payments: {total_pay}")
print(f"Commission 50%: {total_pay * 50 // 100}")

try:
    sal = json.loads((base / "handler_salaries.json").read_text(encoding="utf-8"))
    for row in sal.get("salaries", []):
        if ref_key(row.get("reference")) == HANDLER:
            print(f"Salary record: monthly {row.get('monthly_salary')} owed_for_month {row.get('owed')}")
except FileNotFoundError:
    print("No handler_salaries.json")

try:
    expf = json.loads((base / "handler_expenses.json").read_text(encoding="utf-8"))
    paid = 0
    for e in expf.get("expenses", []):
        if ref_key(e.get("reference")) != HANDLER:
            continue
        if not (e.get("date") or "").startswith(month):
            continue
        amt = int(e.get("amount") or 0)
        paid += amt
        print(f"Payout {e.get('date')}: {amt} ({e.get('category')}) {e.get('note','')[:50]}")
    print(f"Total paid out in {month}: {paid}")
except FileNotFoundError:
    print("No handler_expenses.json")
'''

    sftp = client.open_sftp()
    remote = f"{REMOTE}/scripts/_probe_thrilok_tmp.py"
    with sftp.file(remote, "w") as f:
        f.write(script)
    sftp.close()

    _, stdout, stderr = client.exec_command(f"python3 {remote}", timeout=60)
    print(stdout.read().decode("utf-8", errors="replace"))
    err = stderr.read().decode("utf-8", errors="replace")
    if err.strip():
        print("stderr:", err[:500])
    client.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
