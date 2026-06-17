#!/usr/bin/env python3
"""Remove Keerthana bulk-imported telegram group rows (not real leads)."""
from __future__ import annotations
import os, socket, sys
import paramiko

HOST, USER = "187.127.169.159", "root"
PWD = os.environ.get("VPS_PASSWORD", "")

def ssh_run(script: str, timeout=180) -> str:
    sock = socket.create_connection((HOST, 22), timeout=30)
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(hostname=HOST, username=USER, password=PWD, sock=sock)
    cmd = f"cd /opt/telegramforward.old && source venv/bin/activate && python3 << 'PYEOF'\n{script}\nPYEOF"
    _, o, e = c.exec_command(cmd, timeout=timeout)
    out = o.read().decode("utf-8", errors="replace")
    err = e.read().decode("utf-8", errors="replace")
    c.close()
    return out + ("\nSTDERR: " + err if err.strip() else "")

DELETE = r'''
import os, json, shutil
from datetime import datetime, timezone

STAMP = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
ROOT = "/opt/telegramforward.old"
BACKUP = f"{ROOT}/backups/pre_keerthana_delete_{STAMP}"
os.makedirs(BACKUP, exist_ok=True)

from dotenv import load_dotenv
load_dotenv(f"{ROOT}/.env")
import psycopg2

os.system(f'pg_dump "$DATABASE_URL" -t candidates_store -f {BACKUP}/candidates_store.sql')

conn = psycopg2.connect(os.environ["DATABASE_URL"])
cur = conn.cursor()

cur.execute("""
  SELECT id, payload FROM candidates_store
  WHERE lower(payload->>'reference') LIKE '%keerth%'
""")
rows = cur.fetchall()
ids = [r[0] for r in rows]
print(f"found {len(ids)} Keerthana rows to delete")

# backup payloads as json
backup_rows = []
for cid, payload in rows:
    p = payload if isinstance(payload, dict) else json.loads(payload)
    backup_rows.append({"id": cid, **p})
with open(f"{BACKUP}/keerthana_deleted.json", "w") as f:
    json.dump(backup_rows, f, indent=2)

cur.execute("""
  DELETE FROM candidates_store
  WHERE lower(payload->>'reference') LIKE '%keerth%'
""")
deleted = cur.rowcount
conn.commit()

cur.execute("SELECT COUNT(*) FROM candidates_store")
remaining = cur.fetchone()[0]
cur.execute("""
  SELECT payload->>'reference', COUNT(*)
  FROM candidates_store GROUP BY 1 ORDER BY 2 DESC
""")
print(f"deleted: {deleted}, remaining candidates: {remaining}")
print("references left:", cur.fetchall())
conn.close()

proofs = f"{ROOT}/data/candidates_proofs"
removed = 0
if os.path.isdir(proofs):
    for cid in ids:
        p = os.path.join(proofs, str(cid))
        if os.path.isdir(p):
            shutil.rmtree(p, ignore_errors=True)
            removed += 1
print(f"proof folders removed: {removed}")
print("BACKUP:", BACKUP)
print("DONE")
'''

if __name__ == "__main__":
    if not PWD:
        sys.exit("Set VPS_PASSWORD")
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    print(ssh_run(DELETE))
