#!/usr/bin/env python3
import os, socket, sys, paramiko
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
HOST, USER = "187.127.169.159", "root"
PWD = os.environ.get("VPS_PASSWORD", "")
ROOT = "/opt/telegramforward.old"
REMOTE = f"{ROOT}/scripts/_explain_pavan.py"

SCRIPT = r'''import json, os, sys
sys.path.insert(0, "/opt/telegramforward.old")
os.chdir("/opt/telegramforward.old")
from features.candidate_store import list_candidates, stats, _row_month

rows = list_candidates(reference="Pavan Kalyan")
print("=== Pavan candidates (payment field) ===")
for c in sorted(rows, key=lambda x: x.get("date") or ""):
    pay = int(c.get("payment") or 0)
    exp = int(c.get("expected_payment") or 0)
    hs = pay * 50 // 100
    print(f"- {c.get('name')} | {c.get('stage')} | payment={pay} | expected={exp} | 50%={hs} | {c.get('date')} | month={_row_month(c)}")

print("\nTotals:")
print("sum payment", sum(int(c.get("payment") or 0) for c in rows))
print("sum 50%", sum(int(c.get("payment") or 0) * 50 // 100 for c in rows))

print("\nBy month:")
for m in ["2026-05", "2026-06", None]:
    sub = rows if m is None else [c for c in rows if _row_month(c) == m]
    sp = sum(int(c.get("payment") or 0) for c in sub)
    sc = sp * 50 // 100
    label = m or "all"
    s = stats(month=m, reference="Pavan Kalyan")
    tp = next((p for p in s.get("top_performers",[]) if "pavan" in (p.get("name") or "").lower()), {})
    print(f"{label}: payments={sp} commission_calc={sc} stats_comm={tp.get('commission_total')} paid={tp.get('paid_out_total')} owe={tp.get('net_payable')}")
'''

sock = socket.create_connection((HOST, 22), timeout=30)
c = paramiko.SSHClient(); c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(hostname=HOST, username=USER, password=PWD, sock=sock)
sftp = c.open_sftp()
with sftp.open(REMOTE, "w") as f:
    f.write(SCRIPT.encode("utf-8"))
sftp.close()
_, o, e = c.exec_command(f"{ROOT}/venv/bin/python3 {REMOTE}", timeout=120)
print(o.read().decode("utf-8", errors="replace"))
c.exec_command(f"rm -f {REMOTE}")
c.close()
