#!/usr/bin/env python3
from __future__ import annotations
import os, socket, sys
import paramiko

HOST, USER = "187.127.169.159", "root"
PWD = os.environ.get("VPS_PASSWORD", "")

def ssh_run(script: str, timeout=300) -> str:
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

PRUNE = r'''
import os, json, re, shutil
from datetime import datetime, timezone

STAMP = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
ROOT = "/opt/telegramforward.old"
BACKUP = f"{ROOT}/backups/pre_prune_{STAMP}"
KEEP = ("2026-05", "2026-06")
os.makedirs(BACKUP, exist_ok=True)

from dotenv import load_dotenv
load_dotenv(f"{ROOT}/.env")
import psycopg2

for fn in ["handler_expenses.json", "handler_salaries.json", "candidates.json"]:
    src = f"{ROOT}/data/{fn}"
    if os.path.exists(src):
        shutil.copy2(src, f"{BACKUP}/{fn}")

os.system(f'pg_dump "$DATABASE_URL" -t candidates_store -t crm_leads -t inbox_messages -t inbox_conversations -f {BACKUP}/prune_tables.sql')

conn = psycopg2.connect(os.environ["DATABASE_URL"])
cur = conn.cursor()

cur.execute("SELECT COUNT(*) FROM candidates_store")
before = cur.fetchone()[0]
cur.execute("""
    DELETE FROM candidates_store
    WHERE COALESCE(
        NULLIF(substring(payload->>'date' from '^\\d{4}-\\d{2}'), ''),
        NULLIF(substring(payload->>'created_at' from '^\\d{4}-\\d{2}'), ''),
        to_char(updated_at, 'YYYY-MM')
    ) NOT IN ('2026-05', '2026-06')
""")
del_cand = cur.rowcount
cur.execute("SELECT COUNT(*) FROM candidates_store")
after = cur.fetchone()[0]
print(f"candidates_store: {before} -> {after} (deleted {del_cand})")

cur.execute("SELECT id FROM candidates_store")
kept_ids = {r[0] for r in cur.fetchall()}

cur.execute("SELECT COUNT(*) FROM crm_leads")
b = cur.fetchone()[0]
cur.execute("""
    DELETE FROM crm_leads
    WHERE to_char(created_at, 'YYYY-MM') NOT IN ('2026-05', '2026-06')
""")
del_crm = cur.rowcount
cur.execute("SELECT COUNT(*) FROM crm_leads")
print(f"crm_leads: {b} -> {cur.fetchone()[0]} (deleted {del_crm})")

cur.execute("""
    SELECT column_name FROM information_schema.columns
    WHERE table_name='inbox_messages'
""")
msg_cols = [r[0] for r in cur.fetchall()]
ts_col = next((c for c in msg_cols if c in ('msg_timestamp','ts','timestamp','created_at','sent_at','message_at')), None)
if ts_col:
    cur.execute("SELECT COUNT(*) FROM inbox_messages")
    b = cur.fetchone()[0]
    cur.execute(f"""
        DELETE FROM inbox_messages
        WHERE to_char({ts_col}, 'YYYY-MM') NOT IN ('2026-05', '2026-06')
    """)
    del_msg = cur.rowcount
    cur.execute("SELECT COUNT(*) FROM inbox_messages")
    print(f"inbox_messages ({ts_col}): {b} -> {cur.fetchone()[0]} (deleted {del_msg})")
else:
    print("inbox_messages cols:", msg_cols, "- skipped")

cur.execute("SELECT COUNT(*) FROM inbox_conversations")
b = cur.fetchone()[0]
cur.execute("""
    DELETE FROM inbox_conversations
    WHERE to_char(last_message_at, 'YYYY-MM') NOT IN ('2026-05', '2026-06')
""")
del_conv = cur.rowcount
cur.execute("SELECT COUNT(*) FROM inbox_conversations")
print(f"inbox_conversations: {b} -> {cur.fetchone()[0]} (deleted {del_conv})")

conn.commit()
conn.close()

def in_keep(val):
    if not val: return False
    m = re.match(r"(\d{4})-(\d{2})", str(val))
    return m and f"{m.group(1)}-{m.group(2)}" in KEEP

path = f"{ROOT}/data/handler_expenses.json"
if os.path.exists(path):
    with open(path) as f:
        data = json.load(f)
    if isinstance(data, list):
        kept = [r for r in data if in_keep(r.get("date") or r.get("month"))]
        with open(path, "w") as f:
            json.dump(kept, f, indent=2)
        print(f"handler_expenses.json: kept {len(kept)}, deleted {len(data)-len(kept)}")
    elif isinstance(data, dict):
        kept = {k: v for k, v in data.items() if in_keep(k) or in_keep((v or {}).get("date") if isinstance(v, dict) else None)}
        with open(path, "w") as f:
            json.dump(kept, f, indent=2)
        print(f"handler_expenses.json: kept {len(kept)}, deleted {len(data)-len(kept)} keys")

proofs = f"{ROOT}/data/candidates_proofs"
removed = 0
if os.path.isdir(proofs):
    for cid in os.listdir(proofs):
        if cid not in kept_ids:
            shutil.rmtree(os.path.join(proofs, cid), ignore_errors=True)
            removed += 1
    print(f"candidates_proofs folders removed: {removed}")

print("BACKUP:", BACKUP)
print("DONE")
'''

if __name__ == "__main__":
    if not PWD:
        sys.exit("Set VPS_PASSWORD")
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    print(ssh_run(PRUNE))
