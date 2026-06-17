#!/usr/bin/env python3
import os, socket, sys, json
import paramiko
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
PASSWORD = os.environ.get("VPS_PASSWORD", "")
SCRIPT = (
    "import json, sys, urllib.request\n"
    "sys.path.insert(0, '/opt/telegramforward.old')\n"
    "from core.dashboard_auth_vps import get_credentials, create_session_token, SESSION_COOKIE\n"
    "user, pw = get_credentials()\n"
    "token = create_session_token(user, role='admin')\n"
    "req = urllib.request.Request('http://127.0.0.1:8000/state')\n"
    "req.add_header('Cookie', f'{SESSION_COOKIE}={token}')\n"
    "state = json.loads(urllib.request.urlopen(req, timeout=20).read())\n"
    "for slot in ['account9','account6','account1']:\n"
    "    a = state.get('account_states', {}).get(slot, {})\n"
    "    print('===', slot, '===')\n"
    "    print('top success/failed:', a.get('success'), a.get('failed'))\n"
    "    print('forwarding nested:', json.dumps(a.get('forwarding')))\n"
    "    print('campaign nested:', json.dumps(a.get('campaign')))\n"
)
sock = socket.create_connection(("187.127.169.159", 22), timeout=30)
c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(hostname="187.127.169.159", username="root", password=PASSWORD, sock=sock)
sftp = c.open_sftp()
with sftp.open("/tmp/nested.py", "w") as f:
    f.write(SCRIPT)
sftp.close()
_, stdout, _ = c.exec_command("/opt/telegramforward.old/venv/bin/python /tmp/nested.py 2>&1", timeout=30)
print(stdout.read().decode())
c.close()
