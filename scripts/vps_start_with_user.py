#!/usr/bin/env python3
import os, socket, sys, time
import paramiko
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
PASSWORD = os.environ.get("VPS_PASSWORD", "")
REMOTE = "/opt/telegramforward.old"

SCRIPT = '''
import json, time, urllib.request, base64
from pathlib import Path

user = pw = ""
for line in Path("/opt/telegramforward.old/.env").read_text().splitlines():
    if line.startswith("DASHBOARD_USERNAME="):
        user = line.split("=", 1)[1].strip().strip('"').strip("'")
    if line.startswith("DASHBOARD_PASSWORD="):
        pw = line.split("=", 1)[1].strip().strip('"').strip("'")
print("user", user, "pw_len", len(pw))

def post(path):
    req = urllib.request.Request("http://127.0.0.1:8000" + path, method="POST", data=b"")
    req.add_header("Authorization", "Basic " + base64.b64encode(f"{user}:{pw}".encode()).decode())
    with urllib.request.urlopen(req, timeout=20) as r:
        return r.read().decode()

for slot in ["account3", "account5", "account8", "account10"]:
    try:
        print(slot, post(f"/account/{slot}/start?feature=campaign"))
    except Exception as e:
        print(slot, "ERR", e)

print("sleep 200s")
time.sleep(200)
for slot in ["account3", "account5", "account8", "account10"]:
    p = Path(f"/opt/telegramforward.old/data/accounts/{slot}/cycle_metrics_last.json")
    cm = json.loads(p.read_text())
    age = int(time.time() - float(cm.get("ended_at") or 0))
    print(f"{slot}: success={cm.get('success')} skipped={cm.get('skipped')} cycle={cm.get('cycle_number')} age={age}s")
print("running:", Path("/opt/telegramforward.old/data/.running_workers.json").read_text())
'''

sock = socket.create_connection(("187.127.169.159", 22), timeout=30)
c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(hostname="187.127.169.159", username="root", password=PASSWORD, sock=sock)
sftp = c.open_sftp()
with sftp.open("/tmp/start_real.py", "w") as f:
    f.write(SCRIPT)
sftp.close()
_, stdout, _ = c.exec_command(f"{REMOTE}/venv/bin/python /tmp/start_real.py 2>&1", timeout=240)
print(stdout.read().decode())
c.close()
