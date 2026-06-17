#!/usr/bin/env python3
"""Query Postgres structured logs for skip/fail reasons during shutdown idle windows."""
from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone

import paramiko

HOST = "187.127.169.159"
USER = "root"
PASSWORD = os.environ.get("VPS_PASSWORD", "")
ROOT = "/opt/telegramforward.old"

# Idle windows: (last_send_or_window_start, shutdown_at) UTC unix
WINDOWS = {
    "account1": {
        "name": "Vani_support",
        "start": 1780208563.19,   # last send 2026-05-31 06:22:43
        "end": 1780257818.36,     # shutdown 2026-05-31 20:03:38
    },
    "account2": {
        "name": "Karthik Prasad",
        "start": 1780200422.88,   # last send 2026-05-31 04:07:02
        "end": 1780257818.52,
    },
    "account4": {
        "name": "Shiva",
        "start": 1779953903.55,   # last send 2026-05-28 07:38:23
        "end": 1780048247.83,     # shutdown 2026-05-29 09:50:47
    },
    "account8": {
        "name": "New Gen INTERVIEW SUPPORT",
        "start": 1780048247.85 - 22 * 3600,  # ~21h before shutdown (Path C)
        "end": 1780048247.85,
    },
}

REMOTE = r'''
import json, os, sys, time
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path("/opt/telegramforward.old")
sys.path.insert(0, str(ROOT))
os.chdir(ROOT)

WINDOWS = json.loads(os.environ["WINDOWS_JSON"])

def iso(ts):
    if ts is None: return None
    if hasattr(ts, "isoformat"): return ts.isoformat()
    return datetime.fromtimestamp(float(ts), tz=timezone.utc).isoformat()

env = {}
for ln in (ROOT/".env").read_text().splitlines():
    if "=" in ln and not ln.strip().startswith("#"):
        k,v = ln.split("=",1); env[k.strip()] = v.strip().strip('"')

import psycopg2, psycopg2.extras
conn = psycopg2.connect(env.get("DATABASE_URL") or env.get("POSTGRES_URL"))
cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

cur.execute("SELECT tablename FROM pg_tables WHERE schemaname='public' ORDER BY 1")
tables = [r["tablename"] for r in cur.fetchall()]
print("TABLES:", tables)

def table_info(t):
    cur.execute(
        "SELECT column_name, data_type FROM information_schema.columns WHERE table_name=%s ORDER BY ordinal_position",
        (t,),
    )
    return [(r["column_name"], r["data_type"]) for r in cur.fetchall()]

for t in tables:
    cols = table_info(t)
    print(f"\nSCHEMA {t}:")
    for c, dt in cols:
        print(f"  {c} ({dt})")

# Find best log table
log_table = None
acct_col = ts_col = event_col = reason_col = action_col = group_col = None
for t in tables:
    cols = [c for c,_ in table_info(t)]
    ac = next((c for c in cols if c in ("account_id", "slot", "account")), None)
    tc = next((c for c in cols if c in ("timestamp", "created_at", "ts", "event_time", "logged_at")), None)
    if ac and tc and any(c in cols for c in ("event", "action", "reason", "level", "summary")):
        log_table = t
        acct_col = ac
        ts_col = tc
        event_col = next((c for c in cols if c in ("event", "event_type")), None)
        reason_col = next((c for c in cols if c in ("reason", "skip_reason")), None)
        action_col = next((c for c in cols if c in ("action",)), None)
        group_col = next((c for c in cols if c in ("group_id", "group", "group_name")), None)
        print(f"\nSELECTED LOG TABLE: {t} acct={acct_col} ts={ts_col} event={event_col} reason={reason_col} action={action_col} group={group_col}")
        break

if not log_table:
    # try any table with account_id
    for t in tables:
        cols = [c for c,_ in table_info(t)]
        if "account_id" in cols:
            log_table = t
            acct_col = "account_id"
            ts_col = next((c for c in cols if "time" in c or c in ("timestamp","created_at","ts")), cols[0])
            print(f"\nFALLBACK TABLE: {t}")
            break

if not log_table:
    print("NO LOG TABLE FOUND")
    sys.exit(1)

cols = [c for c,_ in table_info(log_table)]

for slot, win in WINDOWS.items():
    start, end = win["start"], win["end"]
    print("\n" + "=" * 70)
    print(f"SLOT {slot} ({win['name']})")
    print(f"Window: {iso(start)} -> {iso(end)}")
    print("=" * 70)

    sel = ["*"]
    q = f"SELECT * FROM {log_table} WHERE {acct_col}=%s AND {ts_col} >= to_timestamp(%s) AND {ts_col} <= to_timestamp(%s) ORDER BY {ts_col} ASC"
    cur.execute(q, (slot, start, end))
    rows = cur.fetchall()
    print(f"Total rows in window: {len(rows)}")

    if not rows:
        # try without end bound expansion
        cur.execute(
            f"SELECT COUNT(*) AS n FROM {log_table} WHERE {acct_col}=%s",
            (slot,),
        )
        total = cur.fetchone()["n"]
        print(f"  Total rows ever for {slot} in {log_table}: {total}")
        if total:
            cur.execute(
                f"SELECT * FROM {log_table} WHERE {acct_col}=%s ORDER BY {ts_col} DESC LIMIT 10",
                (slot,),
            )
            print("  Last 10 rows (any time):")
            for r in cur.fetchall():
                d = {k: iso(v) if k == ts_col or hasattr(v,'isoformat') else v for k,v in dict(r).items()}
                print("   ", json.dumps(d, default=str)[:500])
        continue

    reason_ctr = Counter()
    action_ctr = Counter()
    event_ctr = Counter()
    sent = fail = skip = 0
    samples = defaultdict(list)

    for r in rows:
        d = dict(r)
        reason = d.get(reason_col) or d.get("reason") or ""
        action = d.get(action_col) or d.get("action") or ""
        event = d.get(event_col) or d.get("event") or ""
        level = d.get("level") or d.get("level_std") or ""
        summary = d.get("summary") or d.get("msg") or ""

        if reason: reason_ctr[str(reason)] += 1
        if action: action_ctr[str(action)] += 1
        if event: event_ctr[str(event)] += 1

        blob = f"{event}|{action}|{reason}|{level}|{summary}".lower()
        if action in ("sent",) or event in ("SENT",) or "sent" in blob and "skip" not in blob:
            sent += 1
        elif "skip" in blob or action == "skipped" or event == "SKIP":
            skip += 1
            key = reason or action or event or "skip"
            if len(samples[key]) < 3:
                samples[key].append(d)
        elif "fail" in blob or level in ("error", "fail", "ERROR", "FAIL"):
            fail += 1
            key = reason or action or event or "fail"
            if len(samples[key]) < 3:
                samples[key].append(d)

    print(f"Summary: sent~{sent} skip~{skip} fail~{fail}")
    print("Top events:", event_ctr.most_common(15))
    print("Top actions:", action_ctr.most_common(15))
    print("Top reasons:", reason_ctr.most_common(15))

    print("\nSample skip/fail rows by reason:")
    for key, items in list(samples.items())[:12]:
        print(f"  -- {key} ({reason_ctr.get(key, action_ctr.get(key, '?'))} hits) --")
        for d in items[:2]:
            out = {k: (iso(v) if k == ts_col else v) for k, v in d.items() if v not in (None, "", {})}
            print("    ", json.dumps(out, default=str)[:450])

# send timestamps from postgres if table exists
for t in tables:
    cols = [c for c,_ in table_info(t)]
    if "timestamps" in cols or t.endswith("send") or "send" in t:
        print(f"\n=== SEND TABLE CANDIDATE {t} ===")
        for slot in WINDOWS:
            ac = next((c for c in cols if c in ("account_id","slot")), None)
            if ac:
                try:
                    cur.execute(f"SELECT * FROM {t} WHERE {ac}=%s LIMIT 3", (slot,))
                    for r in cur.fetchall():
                        print(slot, dict(r))
                except Exception as ex:
                    conn.rollback()

# get_last_post from code
print("\n=== get_last_post_timestamp ===")
try:
    from core.send_stats import get_last_post_timestamp, _load_timestamps
    for slot in WINDOWS:
        lp = get_last_post_timestamp(slot)
        raw = _load_timestamps(slot)
        print(slot, "last_post", iso(lp), "file_timestamps", len(raw))
except Exception as e:
    print("err", e)

conn.close()
print("\nDONE")
'''


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if not PASSWORD:
        raise SystemExit("Set VPS_PASSWORD")

    windows_json = json.dumps(WINDOWS)
    remote_cmd = (
        f"export WINDOWS_JSON='{windows_json}'; "
        f"cd {ROOT} && ./venv/bin/python3 - <<'PY'\n{REMOTE}\nPY"
    )

    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(HOST, username=USER, password=PASSWORD, timeout=30)
    _, stdout, stderr = c.exec_command(remote_cmd, timeout=300)
    out = stdout.read().decode("utf-8", errors="replace")
    err = stderr.read().decode("utf-8", errors="replace")
    code = stdout.channel.recv_exit_status()
    c.close()

    out_path = os.path.join(os.environ.get("TEMP", "."), "postgres_idle_window_logs.txt")
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(out)
        if err.strip():
            f.write("\n\nSTDERR:\n" + err)

    print(out)
    if err.strip():
        print("\nSTDERR:\n", err[:4000], file=sys.stderr)
    print(f"\nSaved: {out_path}")
    if code != 0:
        raise SystemExit(code)


if __name__ == "__main__":
    main()
