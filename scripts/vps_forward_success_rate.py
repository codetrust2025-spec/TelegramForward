#!/usr/bin/env python3
import os, socket, sys
import paramiko
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
PASSWORD = os.environ.get("VPS_PASSWORD", "")
SCRIPT = (
    "import json, sys\n"
    "sys.path.insert(0, '/opt/telegramforward.old')\n"
    "from core.dashboard_auth_vps import get_credentials, create_session_token, SESSION_COOKIE\n"
    "import urllib.request\n"
    "user, pw = get_credentials()\n"
    "token = create_session_token(user, role='admin')\n"
    "req = urllib.request.Request('http://127.0.0.1:8000/state')\n"
    "req.add_header('Cookie', f'{SESSION_COOKIE}={token}')\n"
    "state = json.loads(urllib.request.urlopen(req, timeout=20).read())\n"
    "fwd_success = fwd_failed = fwd_skipped = 0\n"
    "fwd_running = 0\n"
    "for slot, a in (state.get('account_states') or {}).items():\n"
    "    if not a.get('forwarding_running'):\n"
    "        continue\n"
    "    fwd_running += 1\n"
    "    fwd_success += int(a.get('success') or 0)\n"
    "    fwd_failed += int(a.get('failed') or 0)\n"
    "    fwd_skipped += int(a.get('skipped_already_posted') or 0)\n"
    "processed = fwd_success + fwd_failed\n"
    "rate = (fwd_success / processed * 100) if processed else 0\n"
    "print('FORWARDING (session): running=%s success=%s failed=%s rate=%.1f%%' % (fwd_running, fwd_success, fwd_failed, rate))\n"
    "for slot in ['account1','account2','account4','account6','account9']:\n"
    "    a = (state.get('account_states') or {}).get(slot, {})\n"
    "    if not a.get('forwarding_running'):\n"
    "        print(slot, 'not forwarding')\n"
    "        continue\n"
    "    print(slot, 'ok=%s fail=%s status=%s rest=%ss health=%s' % (a.get('success'), a.get('failed'), a.get('status'), a.get('next_cycle_in'), a.get('health_score')))\n"
    "print('notification:', state.get('notification'))\n"
)
sock = socket.create_connection(("187.127.169.159", 22), timeout=30)
c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(hostname="187.127.169.159", username="root", password=PASSWORD, sock=sock)
sftp = c.open_sftp()
with sftp.open("/tmp/fwd_rate.py", "w") as f:
    f.write(SCRIPT)
sftp.close()
_, stdout, _ = c.exec_command("/opt/telegramforward.old/venv/bin/python /tmp/fwd_rate.py 2>&1", timeout=60)
print(stdout.read().decode())
c.close()
