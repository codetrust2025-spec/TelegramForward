#!/usr/bin/env python3
"""Check if UI success counters are always 0 despite real sends."""
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
    "print('TOP LEVEL: success=%s failed=%s total=%s' % (state.get('success'), state.get('failed'), state.get('total')))\n"
    "ac = state.get('account_states') or {}\n"
    "for slot in sorted(ac.keys()):\n"
    "    a = ac[slot]\n"
    "    if not (a.get('forwarding_running') or a.get('campaign_running')):\n"
    "        continue\n"
    "    keys = {k: a.get(k) for k in ['success','failed','forwarding_success','campaign_success',\n"
    "        'forwarding_running','campaign_running','cycle','forward_batch','status']}\n"
    "    print(slot, json.dumps(keys))\n"
    "# Raw worker state via build\n"
    "from services.account_manager import manager\n"
    "for slot in ['account9','account6','account5']:\n"
    "    w = manager.get_worker(slot)\n"
    "    d = w.state.to_dict()\n"
    "    print('RAW', slot, 'success=', d.get('success'), 'failed=', d.get('failed'),\n"
    "          'fwd_ok=', d.get('forwarding_success'), 'camp_ok=', d.get('campaign_success'))\n"
)

sock = socket.create_connection(("187.127.169.159", 22), timeout=30)
c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(hostname="187.127.169.159", username="root", password=PASSWORD, sock=sock)
sftp = c.open_sftp()
with sftp.open("/tmp/always_zero.py", "w") as f:
    f.write(SCRIPT)
sftp.close()
_, stdout, stderr = c.exec_command(
    "cd /opt/telegramforward.old && venv/bin/python /tmp/always_zero.py 2>&1", timeout=60
)
print(stdout.read().decode())
print(stderr.read().decode()[:500])
c.close()
