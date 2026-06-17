#!/usr/bin/env python3
import os, socket, sys, json
import paramiko

HOST, USER = "187.127.169.159", "root"
PWD = os.environ.get("VPS_PASSWORD", "")

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
    return out + ("\n" + err if err.strip() else "")

SCRIPT = r'''
import os, json
from dotenv import load_dotenv
load_dotenv("/opt/telegramforward.old/.env")
import psycopg2
conn = psycopg2.connect(os.environ["DATABASE_URL"])
cur = conn.cursor()
cur.execute("SELECT payload FROM candidates_store WHERE lower(payload->>'reference') LIKE '%ravinder%'")
for r in cur.fetchall():
    p = r[0] if isinstance(r[0], dict) else json.loads(r[0])
    print(p.get("name"), "pay", p.get("payment"), "date", str(p.get("date") or p.get("created_at"))[:10])

from features.candidate_store import stats
for m in ["2026-06","2026-05","all"]:
    s = stats(month=m)
    rav = next((p for p in s["top_performers"] if "ravinder" in (p.get("name") or "").lower()), None)
    print(f"month {m}:", rav and {k: rav[k] for k in ["name","revenue_total","commission_total","salary_total","net_payable"]})
'''

if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    print(ssh_run(SCRIPT))
