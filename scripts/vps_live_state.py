#!/usr/bin/env python3
import os, socket, sys, json
import paramiko
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
PASSWORD = os.environ.get("VPS_PASSWORD", "")
SCRIPT = '''
import json, urllib.request, sys
sys.path.insert(0, "/opt/telegramforward.old")
from core.dashboard_auth_vps import get_credentials, create_session_token, SESSION_COOKIE
user, pw = get_credentials()
token = create_session_token(user, role="admin")
req = urllib.request.Request("http://127.0.0.1:8000/state")
req.add_header("Cookie", f"{SESSION_COOKIE}={token}")
state = json.loads(urllib.request.urlopen(req, timeout=20).read())
for slot in ["account3", "account8", "account5"]:
    a = state.get("accounts", {}).get(slot, {})
    print(json.dumps({
        "slot": slot,
        "running": a.get("running"),
        "campaign_running": a.get("campaign_running"),
        "status": a.get("status"),
        "campaign_status": a.get("campaign_status"),
        "success": a.get("success"),
        "cycle": a.get("cycle"),
        "next_cycle_in": a.get("next_cycle_in"),
        "current_group": a.get("current_group"),
        "health_score": a.get("health_score"),
        "execution_policy": (a.get("execution_policy") or {}).get("unhealthy"),
    }, indent=2))
'''
sock = socket.create_connection(("187.127.169.159", 22), timeout=30)
c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(hostname="187.127.169.159", username="root", password=PASSWORD, sock=sock)
sftp = c.open_sftp()
with sftp.open("/tmp/state_check.py", "w") as f:
    f.write(SCRIPT)
sftp.close()
_, stdout, _ = c.exec_command("/opt/telegramforward.old/venv/bin/python /tmp/state_check.py 2>&1", timeout=30)
print(stdout.read().decode())
c.close()
