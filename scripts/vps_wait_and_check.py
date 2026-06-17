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
user, pw = get_credentials()
token = create_session_token(user, role="admin")
req = urllib.request.Request("http://127.0.0.1:8000/state")
req.add_header("Cookie", f"{SESSION_COOKIE}={token}")
state = json.loads(urllib.request.urlopen(req, timeout=20).read())
ac = state.get("account_states") or {}
for slot in ["account3", "account8", "account5"]:
    a = ac.get(slot, {})
    print(f"LIVE {slot}: cycle={a.get('cycle')} success={a.get('success')} failed={a.get('failed')} skipped={a.get('skipped_already_posted')} status={a.get('status')}")
for slot in ["account3", "account8", "account5"]:
    p = Path(f"/opt/telegramforward.old/data/accounts/{slot}/cycle_metrics_last.json")
    cm = json.loads(p.read_text())
    age = int(time.time() - float(cm.get("ended_at") or 0))
    print(f"DISK {slot}: success={cm.get('success')} skipped={cm.get('skipped')} cycle={cm.get('cycle_number')} age={age}s")
'''
time.sleep(90)
sock = socket.create_connection(("187.127.169.159", 22), timeout=30)
c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(hostname="187.127.169.159", username="root", password=PASSWORD, sock=sock)
sftp = c.open_sftp()
with sftp.open("/tmp/state3.py", "w") as f:
    f.write(SCRIPT)
sftp.close()
_, stdout, _ = c.exec_command("/opt/telegramforward.old/venv/bin/python /tmp/state3.py 2>&1", timeout=30)
print(stdout.read().decode())
c.close()
