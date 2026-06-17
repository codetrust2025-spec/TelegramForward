#!/usr/bin/env python3
import os, socket, sys
import paramiko

HOST, USER = "187.127.169.159", "root"
PWD = os.environ.get("VPS_PASSWORD", "")

def ssh_run(script: str) -> str:
    sock = socket.create_connection((HOST, 22), timeout=30)
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(hostname=HOST, username=USER, password=PWD, sock=sock)
    cmd = f"cd /opt/telegramforward.old && source venv/bin/activate && python3 << 'PYEOF'\n{script}\nPYEOF"
    _, o, _ = c.exec_command(cmd, timeout=120)
    out = o.read().decode("utf-8", errors="replace")
    c.close()
    return out

AUDIT = r'''
import os, json
from dotenv import load_dotenv
load_dotenv("/opt/telegramforward.old/.env")
import psycopg2
conn = psycopg2.connect(os.environ["DATABASE_URL"])
cur = conn.cursor()

for t in ["candidates_meta", "ai_global", "contact_links", "inbox_meta"]:
    cur.execute("SELECT column_name, data_type FROM information_schema.columns WHERE table_name=%s ORDER BY 1", (t,))
    cols = cur.fetchall()
    cur.execute(f"SELECT COUNT(*) FROM {t}")
    n = cur.fetchone()[0]
    print(f"\n{t}: {n} rows, cols={cols}")
    for col, typ in cols:
        if "time" in col or col in ("ts","date","month","created_at","updated_at"):
            try:
                cur.execute(f"SELECT to_char({col}, 'YYYY-MM'), COUNT(*) FROM {t} GROUP BY 1 ORDER BY 1")
                print(f"  {col}:", dict(cur.fetchall()))
            except Exception:
                conn.rollback()
                cur.execute(f"SELECT {col}, COUNT(*) FROM {t} GROUP BY 1 ORDER BY 2 DESC LIMIT 8")
                print(f"  {col}:", cur.fetchall())

conn.close()

for fn in ["handler_salaries.json", "stats_reset.json"]:
    p = f"/opt/telegramforward.old/data/{fn}"
    with open(p) as f:
        d = json.load(f)
    print(f"\n{fn}:", json.dumps(d, indent=2)[:800])
'''

if __name__ == "__main__":
    if not PWD:
        sys.exit("Set VPS_PASSWORD")
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    print(ssh_run(AUDIT))
