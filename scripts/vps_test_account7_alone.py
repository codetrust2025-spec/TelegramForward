#!/usr/bin/env python3
"""Test account7 campaign alone with all others stopped."""
import json, socket, sys, time, urllib.request, http.cookiejar
import paramiko
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
PASSWORD = "REMOVED_VPS_PASSWORD"

REMOTE = r'''
import json, time, urllib.request, http.cookiejar
from pathlib import Path
ROOT = Path("/opt/telegramforward.old")
pw = next(l.split("=",1)[1].strip().strip('"') for l in (ROOT/".env").read_text().splitlines() if l.startswith("DASHBOARD_PASSWORD="))
cj = http.cookiejar.CookieJar()
op = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))
def api(method, path, body=None):
    data = json.dumps(body).encode() if body else None
    req = urllib.request.Request(f"http://127.0.0.1:8000{path}", data=data,
        headers={"Content-Type":"application/json"} if data else {}, method=method)
    with op.open(req, timeout=120) as r:
        return json.loads(r.read().decode())

api("POST", "/auth/login", {"username":"admin","password":pw})
for slot in [f"account{i}" for i in range(1,11)]:
    api("POST", f"/account/{slot}/stop")
    time.sleep(0.2)
time.sleep(5)
print("Starting ONLY account7 campaign...")
api("POST", "/account/account7/start?feature=campaign")
for wait in [20, 40, 60]:
    time.sleep(20)
    st = api("GET", "/state")
    a = st["account_states"]["account7"]
    logs = a.get("logs") or []
    print(f"\n--- after {wait}s ---")
    print(f"status={a.get('status')} groups={len(a.get('my_groups') or [])} sent={a.get('success')} cycle={a.get('cycle')}")
    print(f"notif={a.get('notification')}")
    for lg in logs[-8:]:
        print(f"  {lg if isinstance(lg,str) else lg.get('msg', lg)}")
    if a.get('success', 0) > 0 or (a.get('cycle') or 0) > 0:
        print("SUCCESS - campaign progressing")
        break
    if any("CYCLE_START" in str(lg) for lg in logs[-20:]):
        print("CYCLE_START seen")
        break
'''

sock = socket.create_connection(("187.127.169.159", 22), timeout=30)
c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(hostname="187.127.169.159", username="root", password=PASSWORD, sock=sock)
_, stdout, stderr = c.exec_command(
    f"cd /opt/telegramforward.old && PYTHONPATH=. ./venv/bin/python - <<'PY'\n{REMOTE}\nPY",
    timeout=200,
)
print(stdout.read().decode())
c.close()
