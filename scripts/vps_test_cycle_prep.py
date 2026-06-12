#!/usr/bin/env python3
import socket, paramiko, sys
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
PASSWORD = "REMOVED_VPS_PASSWORD"
REMOTE = r'''
import traceback
try:
    from core.message_rewrite import prepare_cycle_message
except ImportError:
    from workers.account_worker import prepare_cycle_message
from core.groups_store import partition_summary, load_master_groups, groups_readonly_snapshot_for_slot

for slot in ['account7','account3']:
    try:
        m = prepare_cycle_message(slot, 1)
        print(f'{slot} message ok len={len(m)} first_line={m.split(chr(10))[0][:50]}')
    except Exception as e:
        print(f'{slot} message FAIL: {e}')
        traceback.print_exc()
    try:
        p = partition_summary(slot, load_master_groups())
        print(f'{slot} partition ok: groups={p.get("groups")} total={p.get("total_master")}')
    except Exception as e:
        print(f'{slot} partition FAIL: {e}')
        traceback.print_exc()

# Check join restriction
from core.join_cycle import restriction_remaining_seconds
for slot in ['account3','account5','account7','account8','account10']:
    r = restriction_remaining_seconds(slot)
    if r > 0:
        print(f'{slot} JOIN RESTRICTED {r}s')

# Check cycle checkpoint
import os
from pathlib import Path
for slot in CAMPAIGN if False else ['account3','account7']:
    cp = Path(f'/opt/telegramforward.old/data/accounts/{slot}/cycle_checkpoint.json')
    if cp.exists():
        print(f'{slot} checkpoint: {cp.read_text()[:200]}')
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
print(stderr.read().decode())
c.close()
