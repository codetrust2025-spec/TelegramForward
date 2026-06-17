#!/usr/bin/env python3
import socket, paramiko, sys, json
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
PASSWORD = "REMOVED_VPS_PASSWORD"
sock = socket.create_connection(("187.127.169.159", 22), timeout=30)
c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(hostname="187.127.169.159", username="root", password=PASSWORD, sock=sock)
script = '''
import json
from pathlib import Path
from core.fleet_defaults import get_fleet_defaults
from core.posting_mode import load_posting_mode
d = get_fleet_defaults()
print("Bulk default link:", d.get("forward_source_url"))
for slot in ["account1","account2","account4","account6","account9"]:
    pm = load_posting_mode(slot)
    f = pm.forwarding if hasattr(pm, "forwarding") else None
    print(f"{slot}: peer={getattr(f,'source_peer',None)} id={getattr(f,'source_message_id',None)} fwd={pm.forwarding_enabled}")
'''
_, stdout, _ = c.exec_command(
    f"cd /opt/telegramforward.old && PYTHONPATH=. ./venv/bin/python - <<'PY'\n{script}\nPY", timeout=60)
print(stdout.read().decode())
c.close()
