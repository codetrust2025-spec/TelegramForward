#!/usr/bin/env python3
import os, socket, sys
import paramiko

HOST, USER = "187.127.169.159", "root"
PWD = os.environ.get("VPS_PASSWORD", "")

VERIFY = r'''
from features.candidate_store import stats
for m in ["2026-06", "all"]:
    s = stats(month=m)
    print(f"month={m} net_payout={s['net_handler_payout']}")
    for p in s["top_performers"]:
        print(f"  {p['name']}: net={p['net_payable']} owner={p.get('is_owner')} rev={p['revenue_total']}")
'''

def ssh_run(script: str) -> str:
    sock = socket.create_connection((HOST, 22), timeout=30)
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(hostname=HOST, username=USER, password=PWD, sock=sock)
    cmd = f"cd /opt/telegramforward.old && source venv/bin/activate && python3 << 'PYEOF'\n{script}\nPYEOF"
    _, o, e = c.exec_command(cmd, timeout=60)
    return o.read().decode() + e.read().decode()

if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    print(ssh_run(VERIFY))
