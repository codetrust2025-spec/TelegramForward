#!/usr/bin/env python3
import os, sys
import paramiko

PWD = os.environ.get("VPS_PASSWORD", "")
ROOT = "/opt/telegramforward.old"

REMOTE = r'''
import json, os
from pathlib import Path
ROOT = Path("/opt/telegramforward.old")
print("=== .running_workers.json ===")
p = ROOT / "data/.running_workers.json"
print(p.read_text() if p.exists() else "missing")

print("\n=== send_stats.py ===")
print((ROOT/"core/send_stats.py").read_text())

env = {}
for ln in (ROOT/".env").read_text().splitlines():
    if "=" in ln and not ln.strip().startswith("#"):
        k,v = ln.split("=",1); env[k.strip()] = v.strip().strip('"')
import psycopg2, psycopg2.extras
conn = psycopg2.connect(env.get("DATABASE_URL") or env.get("POSTGRES_URL"))
cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
cur.execute("SELECT tablename FROM pg_tables WHERE schemaname='public' ORDER BY 1")
tables = [r["tablename"] for r in cur.fetchall()]
print("\n=== PG TABLES ===", tables)
for t in tables:
    cur.execute("SELECT column_name FROM information_schema.columns WHERE table_name=%s ORDER BY ordinal_position", (t,))
    cols = [r["column_name"] for r in cur.fetchall()]
    print(t, cols)
    acct = next((c for c in cols if c in ("account_id", "slot", "account")), None)
    if acct:
        for slot in ["account1","account2","account4","account8"]:
            try:
                cur.execute(f"SELECT COUNT(*) AS n FROM {t} WHERE {acct}=%s", (slot,))
                n = cur.fetchone()["n"]
                if n:
                    print(f"  {slot} has {n} rows in {t}")
            except Exception as ex:
                conn.rollback()
# sample recent logs per account from any log-like table
for t in tables:
    cur.execute("SELECT column_name FROM information_schema.columns WHERE table_name=%s", (t,))
    cols = [r["column_name"] for r in cur.fetchall()]
    if not any(c in cols for c in ("event", "action", "level", "reason")):
        continue
    acct = next((c for c in cols if c in ("account_id", "slot")), None)
    ts = next((c for c in cols if c in ("timestamp", "created_at", "ts", "event_time")), None)
    if not acct:
        continue
    print(f"\n=== SAMPLE {t} for account1 idle window ===")
    try:
        q = f"SELECT * FROM {t} WHERE {acct}='account1'"
        if ts:
            q += f" AND {ts} >= '2026-05-31 06:22:43+00' AND {ts} <= '2026-05-31 20:03:38+00'"
        q += f" ORDER BY {ts or cols[0]} DESC LIMIT 20"
        cur.execute(q)
        rows = cur.fetchall()
        print(f"rows: {len(rows)}")
        for r in rows[:15]:
            print(json.dumps({k: (v.isoformat() if hasattr(v,'isoformat') else v) for k,v in dict(r).items()}, default=str)[:400])
    except Exception as ex:
        conn.rollback()
        print("err", ex)
conn.close()
'''

def main():
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect("187.127.169.159", "root", PWD, timeout=30)
    _, o, e = c.exec_command(f"cd {ROOT} && ./venv/bin/python3 - <<'PY'\n{REMOTE}\nPY", timeout=300)
    out = o.read().decode("utf-8", errors="replace")
    err = e.read().decode("utf-8", errors="replace")
    c.close()
    path = os.path.join(os.environ.get("TEMP", "."), "postgres_send_stats.txt")
    open(path, "w", encoding="utf-8").write(out + "\n" + err)
    print(out[:25000])
    if err.strip():
        print("ERR", err[:3000])

if __name__ == "__main__":
    main()
