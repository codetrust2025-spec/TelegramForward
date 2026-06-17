#!/usr/bin/env python3
import os, socket, sys, time
from pathlib import Path
import paramiko
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
PASSWORD = os.environ.get("VPS_PASSWORD", "")
REMOTE = "/opt/telegramforward.old"
LOCAL = Path(r"C:\Users\codet\TelegramForward\core\message_rewrite.py")

sock = socket.create_connection(("187.127.169.159", 22), timeout=30)
c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(hostname="187.127.169.159", username="root", password=PASSWORD, sock=sock)
c.open_sftp().put(str(LOCAL), f"{REMOTE}/core/message_rewrite.py")

SCRIPT = '''
import json, time, urllib.request, sys
from pathlib import Path
sys.path.insert(0, "/opt/telegramforward.old")
from core.dashboard_auth_vps import get_credentials, create_session_token, SESSION_COOKIE
from core.message_rewrite import prepare_cycle_message

user, pw = get_credentials()
token = create_session_token(user, role="admin")

def post(path):
    req = urllib.request.Request("http://127.0.0.1:8000" + path, method="POST", data=b"")
    req.add_header("Cookie", f"{SESSION_COOKIE}={token}")
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read().decode()

for slot in ["account3", "account8"]:
    preview = prepare_cycle_message(slot, 99)
    print(f"{slot} preview tail:", preview.split("\\n")[-3:])
    print(post(f"/account/{slot}/stop?feature=campaign"))
    time.sleep(2)
    print(post(f"/account/{slot}/start?feature=campaign"))

print("sleep 200s")
time.sleep(200)
for slot in ["account3", "account8", "account5"]:
    cm = json.loads(Path(f"/opt/telegramforward.old/data/accounts/{slot}/cycle_metrics_last.json").read_text())
    age = int(time.time() - float(cm.get("ended_at") or 0))
    print(f"{slot}: success={cm.get('success')} skipped={cm.get('skipped')} failed={cm.get('failed')} cycle={cm.get('cycle_number')} age={age}s")
'''
with c.open_sftp() as sftp:
    with sftp.open("/tmp/restart38.py", "w") as f:
        f.write(SCRIPT)
_, stdout, _ = c.exec_command(f"{REMOTE}/venv/bin/python /tmp/restart38.py 2>&1", timeout=240)
print(stdout.read().decode())
c.close()
