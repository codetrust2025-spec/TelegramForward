#!/usr/bin/env python3
import socket, paramiko, sys
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
PASSWORD = "8897870998s@SS"
sock = socket.create_connection(("187.127.169.159", 22), timeout=30)
c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(hostname="187.127.169.159", username="root", password=PASSWORD, sock=sock)

test = r'''
import sys
sys.path.insert(0, "/opt/telegramforward.old")
from core.groups_store import load_master_groups, groups_readonly_snapshot_for_slot, load_account_dead

for slot in ["account3","account5","account7","account8","account10"]:
    master = load_master_groups()
    snap = groups_readonly_snapshot_for_slot(slot)
    invalid, blocked = load_account_dead(slot)
    print(f"{slot}: master={len(master)} snap={len(snap)} blocked={len(blocked)} invalid={len(invalid)}")
    if snap:
        print("  sample:", snap[:3])
'''

_, stdout, stderr = c.exec_command(f"cd /opt/telegramforward.old && ./venv/bin/python3 - <<'PY'\n{test}\nPY", timeout=60)
print(stdout.read().decode(errors="replace"))
print(stderr.read().decode(errors="replace")[:2000])
c.close()
