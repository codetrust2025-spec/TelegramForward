#!/usr/bin/env python3
import os, socket, sys, time
import paramiko
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
PASSWORD = os.environ.get("VPS_PASSWORD", "")
REMOTE = "/opt/telegramforward.old"

sock = socket.create_connection(("187.127.169.159", 22), timeout=30)
c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(hostname="187.127.169.159", username="root", password=PASSWORD, sock=sock)

# Get dashboard password
_, stdout, _ = c.exec_command(f"grep '^DASHBOARD_PASSWORD=' {REMOTE}/.env | head -1", timeout=15)
pw_line = stdout.read().decode().strip()
dash_pw = pw_line.split("=", 1)[1].strip().strip('"').strip("'") if pw_line else ""
print("Dashboard pw found:", bool(dash_pw))

slots = ["account3", "account5", "account8", "account10"]
for slot in slots:
    cmd = (
        f"curl -s -X POST 'http://127.0.0.1:8000/account/{slot}/start?feature=campaign' "
        f"-u 'admin:{dash_pw}'"
    )
    _, stdout, _ = c.exec_command(cmd, timeout=20)
    print(f"start {slot}:", stdout.read().decode()[:150])

time.sleep(150)

VERIFY = '''
import json, time
from pathlib import Path
for slot in ["account3", "account5", "account8", "account10"]:
    p = Path(f"/opt/telegramforward.old/data/accounts/{slot}/cycle_metrics_last.json")
    if p.exists():
        cm = json.loads(p.read_text())
        age = int(time.time() - float(cm.get("ended_at") or 0))
        print(f"{slot}: success={cm.get('success')} failed={cm.get('failed')} skipped={cm.get('skipped')} "
              f"groups={cm.get('groups_processed')} cycle={cm.get('cycle_number')} age_sec={age}")
rw = Path("/opt/telegramforward.old/data/.running_workers.json")
print("running_workers:", rw.read_text() if rw.exists() else "[]")
'''
from pathlib import Path
sftp = c.open_sftp()
with sftp.open("/tmp/verify2.py", "w") as f:
    f.write("from pathlib import Path\n" + VERIFY.split("from pathlib import Path\n", 1)[1])
sftp.close()
_, stdout, _ = c.exec_command(f"{REMOTE}/venv/bin/python /tmp/verify2.py", timeout=30)
print("\n=== After 150s ===")
print(stdout.read().decode())
c.close()
