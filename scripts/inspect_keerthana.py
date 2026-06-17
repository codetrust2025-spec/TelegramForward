#!/usr/bin/env python3
import os, socket, sys
import paramiko

HOST, USER = "187.127.169.159", "root"
PWD = os.environ.get("VPS_PASSWORD", "")

def ssh_run(cmd: str) -> str:
    sock = socket.create_connection((HOST, 22), timeout=30)
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(hostname=HOST, username=USER, password=PWD, sock=sock)
    _, o, e = c.exec_command(cmd, timeout=120)
    out = o.read().decode("utf-8", errors="replace")
    err = e.read().decode("utf-8", errors="replace")
    c.close()
    return out + ("\n" + err if err.strip() else "")

SCRIPT = r'''
import os, json
from collections import Counter
from dotenv import load_dotenv
load_dotenv("/opt/telegramforward.old/.env")
import psycopg2
conn = psycopg2.connect(os.environ["DATABASE_URL"])
cur = conn.cursor()

cur.execute("""
  SELECT payload->>'created_at', payload->>'name', payload->>'reference'
  FROM candidates_store
  WHERE lower(payload->>'reference') LIKE '%keerth%'
  ORDER BY payload->>'created_at' LIMIT 5
""")
print("earliest:", cur.fetchall())
cur.execute("""
  SELECT payload->>'created_at', COUNT(*)
  FROM candidates_store
  WHERE lower(payload->>'reference') LIKE '%keerth%'
  GROUP BY 1 ORDER BY 1
""")
print("by created_at day:", cur.fetchall()[:10], "...")

cur.execute("SELECT column_name FROM information_schema.columns WHERE table_name='crm_leads'")
crm_cols = [r[0] for r in cur.fetchall()]
print("crm cols:", crm_cols)
ref_col = next((c for c in crm_cols if "reference" in c or "owner" in c or "handler" in c), None)
if ref_col:
    cur.execute(f"SELECT COUNT(*) FROM crm_leads WHERE lower({ref_col}) LIKE '%keerth%'")
    print(f"crm_leads via {ref_col}:", cur.fetchone()[0])

# real people vs telegram groups
cur.execute("""
  SELECT
    SUM(CASE WHEN payload->>'phone' != '' THEN 1 ELSE 0 END) as with_phone,
    SUM(CASE WHEN payload->>'phone' = '' OR payload->>'phone' IS NULL THEN 1 ELSE 0 END) as no_phone
  FROM candidates_store WHERE lower(payload->>'reference') LIKE '%keerth%'
""")
print("phone breakdown:", cur.fetchone())

# who imported - check bulk endpoint logs or notes
cur.execute("""
  SELECT DISTINCT left(payload->>'created_at', 10), COUNT(*)
  FROM candidates_store WHERE lower(payload->>'reference') LIKE '%keerth%'
  GROUP BY 1
""")
print("import dates:", cur.fetchall())

cur.execute("""
  SELECT payload->>'reference', COUNT(*)
  FROM candidates_store GROUP BY 1 ORDER BY 2 DESC
""")
print("all references:", cur.fetchall())

conn.close()
'''

if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    print("=== STATS LOGIC ===")
    print(ssh_run("grep -n expected_payment /opt/telegramforward.old/features/candidate_store.py | head -20"))
    print("=== DATA ===")
    print(ssh_run(f"cd /opt/telegramforward.old && source venv/bin/activate && python3 << 'PYEOF'\n{SCRIPT}\nPYEOF"))
