#!/usr/bin/env python3
import socket, paramiko, sys
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
PASSWORD = "REMOVED_VPS_PASSWORD"
sock = socket.create_connection(("187.127.169.159", 22), timeout=30)
c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(hostname="187.127.169.159", username="root", password=PASSWORD, sock=sock)
cmds = [
    "grep -iE 'Cycle error|Unexpected error|account7|account3|partition|prepare_cycle|GROUP_SOURCE' /root/.pm2/logs/telegram-backend-out.log | tail -40",
    """cd /opt/telegramforward.old && set -a && . ./.env && set +a && PYTHONPATH=. ./venv/bin/python - <<'PY'
from core.cycle_message import prepare_cycle_message
from core.groups_store import partition_summary, load_master_groups, groups_readonly_snapshot_for_slot
for slot in ['account7','account3']:
    try:
        m = prepare_cycle_message(slot, 1)
        print(f'{slot} message ok len={len(m)}')
    except Exception as e:
        print(f'{slot} message FAIL: {e}')
    try:
        p = partition_summary(slot, load_master_groups())
        print(f'{slot} partition ok: {p}')
    except Exception as e:
        print(f'{slot} partition FAIL: {e}')
    print(f'{slot} snap={len(groups_readonly_snapshot_for_slot(slot))}')
PY""",
]
for cmd in cmds:
    print("===", cmd[:60])
    _, stdout, _ = c.exec_command(cmd, timeout=60)
    print(stdout.read().decode("utf-8", errors="replace")[:8000])
    print()
c.close()
