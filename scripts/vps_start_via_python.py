#!/usr/bin/env python3
import os, socket, sys, time
import paramiko
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
PASSWORD = os.environ.get("VPS_PASSWORD", "")
REMOTE = "/opt/telegramforward.old"

START = '''
import asyncio
import json
import time
import urllib.request
import base64
from pathlib import Path

# read password
env = Path("/opt/telegramforward.old/.env").read_text()
dash_pw = ""
for line in env.splitlines():
    if line.startswith("DASHBOARD_PASSWORD="):
        dash_pw = line.split("=", 1)[1].strip().strip('"').strip("'")
        break
print("pw len", len(dash_pw))

def api_post(path):
    url = "http://127.0.0.1:8000" + path
    req = urllib.request.Request(url, method="POST", data=b"")
    cred = base64.b64encode(f"admin:{dash_pw}".encode()).decode()
    req.add_header("Authorization", f"Basic {cred}")
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return resp.read().decode()
    except Exception as e:
        return str(e)

for slot in ["account3", "account5", "account8", "account10"]:
    print(slot, api_post(f"/account/{slot}/start?feature=campaign"))

print("sleep 150s")
time.sleep(150)

for slot in ["account3", "account5", "account8", "account10"]:
    p = Path(f"/opt/telegramforward.old/data/accounts/{slot}/cycle_metrics_last.json")
    if p.exists():
        cm = json.loads(p.read_text())
        age = int(time.time() - float(cm.get("ended_at") or 0))
        print(f"{slot}: success={cm.get('success')} skipped={cm.get('skipped')} age={age}s cycle={cm.get('cycle_number')}")
'''

sock = socket.create_connection(("187.127.169.159", 22), timeout=30)
c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(hostname="187.127.169.159", username="root", password=PASSWORD, sock=sock)
sftp = c.open_sftp()
with sftp.open("/tmp/start_api.py", "w") as f:
    f.write(START)
sftp.close()
_, stdout, _ = c.exec_command(f"{REMOTE}/venv/bin/python /tmp/start_api.py 2>&1", timeout=200)
print(stdout.read().decode())
c.close()
