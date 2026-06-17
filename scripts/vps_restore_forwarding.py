#!/usr/bin/env python3
"""Restore forwarding accounts after accidental bulk campaign apply."""
import json, os, socket, sys, time, urllib.error, urllib.request, http.cookiejar
import paramiko

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
PASSWORD = "REMOVED_VPS_PASSWORD"
FWD = ["account1", "account2", "account4", "account6", "account9"]
PEER, MSG_ID = "@jobsupport0", 161879

REMOTE = f'''
import json, os, sys, time, urllib.request, http.cookiejar
from pathlib import Path
ROOT = Path("/opt/telegramforward.old")
for line in (ROOT / ".env").read_text().splitlines():
    if "=" in line and not line.strip().startswith("#"):
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))

from core.posting_mode import set_posting_mode, set_forwarding_source

pw = os.environ.get("DASHBOARD_PASSWORD", "")
cj = http.cookiejar.CookieJar()
op = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))
def call(method, path, body=None):
    data = json.dumps(body).encode() if body else None
    req = urllib.request.Request(f"http://127.0.0.1:8000{{path}}", data=data,
        headers={{"Content-Type": "application/json"}} if data else {{}}, method=method)
    with op.open(req, timeout=60) as r:
        return json.loads(r.read().decode())

call("POST", "/auth/login", {{"username": "admin", "password": pw}})
fwd = {json.dumps(FWD)}
for slot in fwd:
    call("POST", f"/account/{{slot}}/stop")
    time.sleep(1)
    set_posting_mode(slot, "forwarding", campaign_enabled=False, forwarding_enabled=True)
    set_forwarding_source(slot, source_peer="{PEER}", source_message_id={MSG_ID})
    out = call("POST", f"/account/{{slot}}/start?feature=forwarding")
    print(slot, "-> forwarding", out.get("status"))
    time.sleep(2)
print("Done restoring forwarding accounts")
'''

sock = socket.create_connection(("187.127.169.159", 22), timeout=30)
c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(hostname="187.127.169.159", username="root", password=PASSWORD, sock=sock)
_, stdout, stderr = c.exec_command(
    f"cd /opt/telegramforward.old && set -a && . ./.env && set +a && PYTHONPATH=. ./venv/bin/python - <<'PY'\n{REMOTE}\nPY",
    timeout=180,
)
print(stdout.read().decode())
c.close()
