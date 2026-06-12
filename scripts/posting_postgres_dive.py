#!/usr/bin/env python3
"""Query Postgres + worker logs for why posting stopped."""
from __future__ import annotations

import os
import sys

import paramiko

PASSWORD = os.environ.get("VPS_PASSWORD", "")
ROOT = "/opt/telegramforward.old"

REMOTE = r'''
import json, os, sys, time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path("/opt/telegramforward.old")
sys.path.insert(0, str(ROOT))
os.chdir(ROOT)

# load env
env = {}
for line in (ROOT / ".env").read_text().splitlines():
    if "=" in line and not line.strip().startswith("#"):
        k, v = line.split("=", 1)
        env[k.strip()] = v.strip().strip('"')

SLOTS = {
    "account1": {"shutdown": 1780257818.36, "last_send": 1780208563.19, "name": "Vani_support"},
    "account2": {"shutdown": 1780257818.52, "last_send": 1780200422.88, "name": "Karthik"},
    "account4": {"shutdown": 1780048247.83, "last_send": 1779953903.55, "name": "Shiva"},
    "account8": {"shutdown": 1780048247.85, "last_send": None, "name": "NewGen"},
}

def iso(ts):
    return datetime.fromtimestamp(float(ts), tz=timezone.utc).isoformat() if ts else None

print("=== send_stats.py get_last_post_timestamp source ===")
src = (ROOT / "core/send_stats.py").read_text()
for i, ln in enumerate(src.splitlines(), 1):
    if "get_last_post" in ln or "def record" in ln or "postgres" in ln.lower() or "INSERT" in ln:
        print(f"{i}: {ln}")

print("\n=== group_send_stats.py head ===")
p = ROOT / "core/group_send_stats.py"
if p.exists():
    print(p.read_text()[:4000])

print("\n=== Find state dir layout ===")
for p in sorted((ROOT / "data").rglob("*"))[:80]:
    if p.is_file() and any(s in str(p) for s in SLOTS):
        print(p.relative_to(ROOT), p.stat().st_size)

# Postgres via venv
url = env.get("DATABASE_URL") or env.get("POSTGRES_URL")
if not url:
    print("NO DATABASE_URL")
else:
    try:
        import psycopg2
        import psycopg2.extras
    except ImportError:
        # use venv
        vpy = ROOT / "venv/bin/python3"
        print("psycopg2 not in system python - use nested")
        raise SystemExit(0)

    conn = psycopg2.connect(url)
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    cur.execute("SELECT tablename FROM pg_tables WHERE schemaname='public' ORDER BY 1")
    tables = [r["tablename"] for r in cur.fetchall()]
    print("\n=== PG TABLES ===", tables)

    for t in tables:
        cur.execute(
            "SELECT column_name, data_type FROM information_schema.columns WHERE table_name=%s ORDER BY ordinal_position",
            (t,),
        )
        cols = cur.fetchall()
        col_names = [c["column_name"] for c in cols]
        if any(x in col_names for x in ["account_id", "slot", "account"]) and any(
            x in col_names for x in ["timestamp", "created_at", "sent_at", "event", "level", "action"]
        ):
            print(f"\nTABLE {t} cols: {col_names}")
            # sample
            cur.execute(f"SELECT * FROM {t} ORDER BY 1 DESC LIMIT 2")
            for row in cur.fetchall():
                print(" sample:", dict(row))

    # search send/post related tables
    for t in tables:
        cn = " ".join(
            r["column_name"]
            for r in conn.cursor().execute(
                "SELECT column_name FROM information_schema.columns WHERE table_name=%s", (t,)
            )
            or []
        )
    conn.close()
'''

REMOTE2 = r'''
import json, os, sys, time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path("/opt/telegramforward.old")
sys.path.insert(0, str(ROOT))
os.chdir(ROOT)

env = {}
for line in (ROOT / ".env").read_text().splitlines():
    if "=" in line and not line.strip().startswith("#"):
        k, v = line.split("=", 1)
        env[k.strip()] = v.strip().strip('"')
url = env.get("DATABASE_URL") or env.get("POSTGRES_URL")

SLOTS = ["account1", "account2", "account4", "account8"]
WINDOWS = {
    "account1": (1780208563, 1780257818),
    "account2": (1780200422, 1780257818),
    "account4": (1779953903, 1780048247),
    "account8": (1780048247 - 26*3600, 1780048247),
}

import psycopg2, psycopg2.extras
conn = psycopg2.connect(url)
cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

cur.execute("SELECT tablename FROM pg_tables WHERE schemaname='public' ORDER BY 1")
tables = [r["tablename"] for r in cur.fetchall()]
print("TABLES:", tables)

# Try common log/event tables
for t in tables:
    cur.execute(
        "SELECT column_name FROM information_schema.columns WHERE table_name=%s",
        (t,),
    )
    cols = [r["column_name"] for r in cur.fetchall()]
    acct_col = next((c for c in cols if c in ("account_id", "slot", "account")), None)
    ts_col = next((c for c in cols if c in ("timestamp", "created_at", "sent_at", "ts", "event_time")), None)
    if not acct_col:
        continue
    print(f"\n--- {t} account_col={acct_col} ts_col={ts_col} cols={cols}")
    for slot in SLOTS:
        try:
            if ts_col:
                start, end = WINDOWS.get(slot, (0, time.time()))
                cur.execute(
                    f"SELECT * FROM {t} WHERE {acct_col}=%s AND {ts_col} >= to_timestamp(%s) AND {ts_col} <= to_timestamp(%s) ORDER BY {ts_col} DESC LIMIT 15",
                    (slot, start, end),
                )
            else:
                cur.execute(f"SELECT * FROM {t} WHERE {acct_col}=%s LIMIT 5", (slot,))
            rows = cur.fetchall()
            if rows:
                print(f"  {slot}: {len(rows)} rows in idle window")
                for r in rows[:8]:
                    d = dict(r)
                    for k,v in list(d.items()):
                        if isinstance(v, datetime):
                            d[k] = v.isoformat()
                    print("   ", json.dumps(d, default=str)[:500])
        except Exception as e:
            conn.rollback()
            print(f"  {slot} query err: {e}")

# get_last_post from code
try:
    from core.send_stats import get_last_post_timestamp
    for s in SLOTS:
        print(s, "get_last_post", get_last_post_timestamp(s))
except Exception as e:
    print("get_last_post err", e)

# Read send_stats full for postgres path
print("\n=== FULL send_stats.py ===")
print((ROOT/"core/send_stats.py").read_text())

conn.close()
'''

def main():
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect("187.127.169.159", "root", PASSWORD, timeout=30)
    # run in venv python
    cmd = f"cd {ROOT} && ./venv/bin/python3 - <<'PY'\n{REMOTE2}\nPY"
    _, stdout, stderr = c.exec_command(cmd, timeout=300)
    out = stdout.read().decode("utf-8", errors="replace")
    err = stderr.read().decode("utf-8", errors="replace")
    c.close()
    print(out)
    if err.strip():
        print("ERR:", err[:5000])

if __name__ == "__main__":
    main()
