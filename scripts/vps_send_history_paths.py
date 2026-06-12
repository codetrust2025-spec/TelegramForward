#!/usr/bin/env python3
import os, socket, sys, json
import paramiko

PASSWORD = os.environ.get("VPS_PASSWORD", "")

def run(cmd, timeout=120):
    sock = socket.create_connection(("187.127.169.159", 22), timeout=30)
    t = paramiko.Transport(sock)
    t.connect(username="root", password=PASSWORD)
    ch = t.open_session()
    ch.settimeout(timeout)
    ch.exec_command(cmd)
    out = b""
    while True:
        if ch.recv_ready():
            out += ch.recv(65535)
        if ch.exit_status_ready():
            while ch.recv_ready():
                out += ch.recv(65535)
            break
    t.close()
    return out.decode("utf-8", errors="replace")

REMOTE = r'''
import json, os, sys
from pathlib import Path
ROOT = Path("/opt/telegramforward.old")
sys.path.insert(0, str(ROOT)); os.chdir(ROOT)

print("=== send_stats get_last_send + paths ===")
from core import send_stats as ss
import inspect
for fn in ["get_last_send_timestamp", "_stats_path", "_load_timestamps", "record_send"]:
    if hasattr(ss, fn):
        print(f"\n--- {fn} ---")
        print(inspect.getsource(getattr(ss, fn)))

print("\n=== group_send_stats ===")
from core import group_send_stats as gs
print(inspect.getsource(gs.get_last_group_send_timestamp))
print(inspect.getsource(gs._stats_path) if hasattr(gs,"_stats_path") else "")

SLOTS = ["account1","account2","account4","account8"]
for s in SLOTS:
    print(f"\n=== {s} send timestamps ===")
    print("  get_last_send:", ss.get_last_send_timestamp(s))
    print("  get_last_post:", ss.get_last_post_timestamp(s))
    try:
        print("  get_last_group_send:", gs.get_last_group_send_timestamp(s))
    except Exception as e:
        print("  group err", e)
    p = ss._stats_path(s)
    print("  send_history path:", p, "exists:", Path(p).exists())
    if Path(p).exists():
        print("  content:", Path(p).read_text()[:1500])
    gp = gs._stats_path(s) if hasattr(gs,"_stats_path") else None
    if gp:
        print("  group_send path:", gp, "exists:", Path(gp).exists())
        if Path(gp).exists():
            print("  content:", Path(gp).read_text()[:1500])

# find all send_history on disk
print("\n=== find send_history ===")
import subprocess
r = subprocess.run(["find", str(ROOT), "-name", "send_history.json", "-o", "-name", "group_send_history.json"], capture_output=True, text=True)
print(r.stdout or r.stderr)

# STATE_DIR from config
from core.config import STATE_DIR, DATA_DIR
print("STATE_DIR:", STATE_DIR)
print("DATA_DIR:", DATA_DIR)
for s in SLOTS:
    d = Path(STATE_DIR) / s
    if d.exists():
        print(f"  {s} state files:", list(d.iterdir()))

# account_logging - where logs go
print("\n=== account_logging ===")
from core import account_logging
print(inspect.getsource(account_logging.account_log)[:2000])

# structured logging sink
from core import structured_logging as sl
src = inspect.getsource(sl.build_log_entry)
print("\nbuild_log_entry (first 1500):", src[:1500])

# Check observability metrics store
print("\n=== metrics snapshot ===")
from core.observability.account_metrics import metrics_store
for s in SLOTS:
    print(s, metrics_store.snapshot(s))
'''

script = f"cd /opt/telegramforward.old && ./venv/bin/python3 - <<'PY'\n{REMOTE}\nPY"
out = run(script, timeout=180)
path = os.path.join(os.environ.get("TEMP","."), "send_history_paths.txt")
open(path,"w",encoding="utf-8").write(out)
print(out)
print("Saved", path)
