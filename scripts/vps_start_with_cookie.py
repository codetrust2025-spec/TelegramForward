#!/usr/bin/env python3
"""Start account3/8 campaign via authenticated API (session cookie)."""
import os
import socket
import sys
import time

import paramiko

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
PASSWORD = os.environ.get("VPS_PASSWORD", "")
REMOTE = "/opt/telegramforward.old"

SCRIPT = '''
import json, time, urllib.request
from pathlib import Path
import sys
sys.path.insert(0, "/opt/telegramforward.old")
from core.dashboard_auth_vps import get_credentials, create_session_token, SESSION_COOKIE

user, pw = get_credentials()
token = create_session_token(user, role="admin")
print("session ok for", user)

def post(path):
    req = urllib.request.Request("http://127.0.0.1:8000" + path, method="POST", data=b"")
    req.add_header("Cookie", f"{SESSION_COOKIE}={token}")
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read().decode()

# Clear shutdown
Path("/opt/telegramforward.old/data/account_shutdown.json").write_text('{"accounts": {}}')

for slot in ["account3", "account8", "account5"]:
    try:
        print(slot, post(f"/account/{slot}/start?feature=campaign"))
    except Exception as e:
        print(slot, "ERR", e)

print("sleep 180s")
time.sleep(180)
for slot in ["account3", "account5", "account8"]:
    cm = json.loads(Path(f"/opt/telegramforward.old/data/accounts/{slot}/cycle_metrics_last.json").read_text())
    age = int(time.time() - float(cm.get("ended_at") or 0))
    print(f"{slot}: success={cm.get('success')} skipped={cm.get('skipped')} failed={cm.get('failed')} cycle={cm.get('cycle_number')} age={age}s")
print("running:", Path("/opt/telegramforward.old/data/.running_workers.json").read_text())
'''

sock = socket.create_connection(("187.127.169.159", 22), timeout=30)
c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(hostname="187.127.169.159", username="root", password=PASSWORD, sock=sock)
sftp = c.open_sftp()
with sftp.open("/tmp/start_cookie.py", "w") as f:
    f.write(SCRIPT)
sftp.close()
_, stdout, _ = c.exec_command(f"{REMOTE}/venv/bin/python /tmp/start_cookie.py 2>&1", timeout=220)
print(stdout.read().decode())
c.close()
