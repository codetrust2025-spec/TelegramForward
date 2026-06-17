#!/usr/bin/env python3
"""Clear shutdown, set running_workers, restart PM2 for auto-resume."""
import os
import socket
import sys
import time

import paramiko

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
PASSWORD = os.environ.get("VPS_PASSWORD", "")
REMOTE = "/opt/telegramforward.old"
CAMPAIGN = ["account3", "account5", "account7", "account8", "account10"]

FIX = f'''
import json
from pathlib import Path

# Clear shutdown for account3/8
sp = Path("{REMOTE}/data/account_shutdown.json")
sp.write_text(json.dumps({{"accounts": {{}}}}, indent=2))

# Persist campaign workers for auto-resume
rw = Path("{REMOTE}/data/.running_workers.json")
rw.write_text(json.dumps({CAMPAIGN!r}, indent=2))
print("running_workers:", rw.read_text())
'''

sock = socket.create_connection(("187.127.169.159", 22), timeout=30)
c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(hostname="187.127.169.159", username="root", password=PASSWORD, sock=sock)

sftp = c.open_sftp()
with sftp.open("/tmp/prep_resume.py", "w") as f:
    f.write(FIX)
sftp.close()

_, stdout, _ = c.exec_command(f"{REMOTE}/venv/bin/python /tmp/prep_resume.py", timeout=20)
print(stdout.read().decode())

print("PM2 restart...")
_, stdout, _ = c.exec_command("pm2 restart telegram-backend", timeout=60)
print(stdout.read().decode()[:400])

print("Waiting 200s for campaign cycles...")
time.sleep(200)

VERIFY = '''
import json, time
from pathlib import Path
for slot in ["account3", "account5", "account8", "account10"]:
    p = Path("/opt/telegramforward.old/data/accounts/" + slot + "/cycle_metrics_last.json")
    cm = json.loads(p.read_text())
    age = int(time.time() - float(cm.get("ended_at") or 0))
    print(f"{slot}: success={cm.get('success')} failed={cm.get('failed')} skipped={cm.get('skipped')} cycle={cm.get('cycle_number')} age={age}s")
print("running:", Path("/opt/telegramforward.old/data/.running_workers.json").read_text())
print("shutdown:", Path("/opt/telegramforward.old/data/account_shutdown.json").read_text())
'''
with c.open_sftp() as sftp:
    with sftp.open("/tmp/verify3.py", "w") as f:
        f.write(VERIFY)
_, stdout, _ = c.exec_command(f"{REMOTE}/venv/bin/python /tmp/verify3.py", timeout=30)
print("\n=== Results ===")
print(stdout.read().decode())

c.close()
