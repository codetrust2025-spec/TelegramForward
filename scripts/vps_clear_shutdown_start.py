#!/usr/bin/env python3
import json, os, socket, sys, time
import paramiko
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
PASSWORD = os.environ.get("VPS_PASSWORD", "")
REMOTE = "/opt/telegramforward.old"

FIX = '''
import json
from pathlib import Path

shutdown_path = Path("/opt/telegramforward.old/data/account_shutdown.json")
print("before:", shutdown_path.read_text() if shutdown_path.exists() else "{}")

data = json.loads(shutdown_path.read_text()) if shutdown_path.exists() else {}
# format may vary
if isinstance(data, dict):
    accounts = data.get("accounts") or data.get("slots") or []
    if isinstance(accounts, dict):
        for slot in ["account3", "account8"]:
            accounts.pop(slot, None)
        data["accounts"] = accounts
    elif isinstance(accounts, list):
        data["accounts"] = [s for s in accounts if s not in ("account3", "account8")]
        if "slots" in data:
            data["slots"] = [s for s in data.get("slots", []) if s not in ("account3", "account8")]
shutdown_path.write_text(json.dumps(data, indent=2))
print("after:", shutdown_path.read_text())

# Use internal API module for auth
import urllib.request, base64
from pathlib import Path
env = Path("/opt/telegramforward.old/.env").read_text()
user = pw = secret = ""
for line in env.splitlines():
    if line.startswith("DASHBOARD_USERNAME="):
        user = line.split("=",1)[1].strip().strip('"').strip("'")
    if line.startswith("DASHBOARD_PASSWORD="):
        pw = line.split("=",1)[1].strip().strip('"').strip("'")
    if line.startswith("DASHBOARD_AUTH_SECRET="):
        secret = line.split("=",1)[1].strip().strip('"').strip("'")

# Try reading auth from dashboard_auth_vps
try:
    import sys
    sys.path.insert(0, "/opt/telegramforward.old")
    from core import dashboard_auth_vps as da
    print("auth module loaded", [x for x in dir(da) if "pass" in x.lower() or "user" in x.lower() or "verify" in x.lower()][:10])
except Exception as e:
    print("auth import err", e)

def try_start(slot, headers_extra=None):
    req = urllib.request.Request(
        f"http://127.0.0.1:8000/account/{slot}/start?feature=campaign",
        method="POST", data=b"",
    )
    req.add_header("Authorization", "Basic " + base64.b64encode(f"{user}:{pw}".encode()).decode())
    if headers_extra:
        for k,v in headers_extra.items():
            req.add_header(k, v)
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            return r.read().decode()
    except Exception as e:
        return str(e)

for slot in ["account3", "account8"]:
    print(slot, try_start(slot))

print("sleep 200")
time.sleep(200)
import json, time
from pathlib import Path
for slot in ["account3", "account8", "account5"]:
    p = Path(f"/opt/telegramforward.old/data/accounts/{slot}/cycle_metrics_last.json")
    cm = json.loads(p.read_text())
    age = int(time.time() - float(cm.get("ended_at") or 0))
    print(f"{slot}: success={cm.get('success')} skipped={cm.get('skipped')} age={age}s cycle={cm.get('cycle_number')}")
print("running:", Path("/opt/telegramforward.old/data/.running_workers.json").read_text())
'''

sock = socket.create_connection(("187.127.169.159", 22), timeout=30)
c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(hostname="187.127.169.159", username="root", password=PASSWORD, sock=sock)
sftp = c.open_sftp()
with sftp.open("/tmp/fix_shutdown.py", "w") as f:
    f.write(FIX)
sftp.close()
_, stdout, _ = c.exec_command(f"{REMOTE}/venv/bin/python /tmp/fix_shutdown.py 2>&1", timeout=240)
print(stdout.read().decode())
c.close()
