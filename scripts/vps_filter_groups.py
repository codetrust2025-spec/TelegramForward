#!/usr/bin/env python3
import socket, paramiko, sys
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
PASSWORD = "8897870998s@SS"
REMOTE = r'''
from core.groups_store import groups_readonly_snapshot_for_slot, load_master_groups
from services.account_manager import manager

# Can't use live workers from separate process - simulate filter logic
for slot in ["account3","account5","account7","account8","account10"]:
    snap = groups_readonly_snapshot_for_slot(slot)
    print(f"{slot}: snapshot={len(snap)}")

# Read _filter_groups logic
import inspect
from workers import account_worker
src = inspect.getsource(account_worker.AccountWorker._filter_groups)
print("\n_filter_groups source (first 1500 chars):")
print(src[:1500])

# load blocked and simulate
from core.groups_store import load_account_dead
for slot in ["account3","account5","account7"]:
    inv, blk = load_account_dead(slot)
    snap = groups_readonly_snapshot_for_slot(slot)
    blocked_set = set(str(x).lower().lstrip("@") for x in blk)
    remaining = [g for g in snap if str(g).lower().lstrip("@") not in blocked_set]
    print(f"{slot}: after removing blocked: {len(remaining)} (blocked={len(blk)})")
'''
sock = socket.create_connection(("187.127.169.159", 22), timeout=30)
c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(hostname="187.127.169.159", username="root", password=PASSWORD, sock=sock)
_, stdout, stderr = c.exec_command(
    f"cd /opt/telegramforward.old && set -a && . ./.env && set +a && PYTHONPATH=. ./venv/bin/python - <<'PY'\n{REMOTE}\nPY",
    timeout=60,
)
print(stdout.read().decode())
print(stderr.read().decode()[-2000:])
c.close()
