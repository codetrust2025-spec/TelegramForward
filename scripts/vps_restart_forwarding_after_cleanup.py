#!/usr/bin/env python3
import os, socket, sys, time
import paramiko
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
PASSWORD = os.environ.get("VPS_PASSWORD", "")
SCRIPT = '''
import json, time, urllib.request, sys
from pathlib import Path
sys.path.insert(0, "/opt/telegramforward.old")
from core.dashboard_auth_vps import get_credentials, create_session_token, SESSION_COOKIE
from core.groups_store import load_master_groups
from core.group_assignment import partition_summary

user, pw = get_credentials()
token = create_session_token(user, role="admin")
def post(path):
    req = urllib.request.Request("http://127.0.0.1:8000" + path, method="POST", data=b"")
    req.add_header("Cookie", f"{SESSION_COOKIE}={token}")
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read().decode()

master = load_master_groups()
for slot in ["account1", "account2", "account4", "account6", "account9"]:
    p = partition_summary(slot, master)
    print(f"{slot} forwarding slice: {p['assigned_count']} groups")

for slot in ["account1", "account2", "account4", "account6", "account9"]:
    try:
        post(f"/account/{slot}/stop?feature=forwarding")
    except Exception:
        pass
time.sleep(2)
for slot in ["account1", "account2", "account4", "account6", "account9"]:
    try:
        print(slot, post(f"/account/{slot}/start?feature=forwarding"))
    except Exception as e:
        print(slot, e)
'''
sock = socket.create_connection(("187.127.169.159", 22), timeout=30)
c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(hostname="187.127.169.159", username="root", password=PASSWORD, sock=sock)
sftp = c.open_sftp()
with sftp.open("/tmp/restart_fwd.py", "w") as f:
    f.write(SCRIPT)
sftp.close()
_, stdout, _ = c.exec_command("/opt/telegramforward.old/venv/bin/python /tmp/restart_fwd.py 2>&1", timeout=60)
print(stdout.read().decode())
c.close()
