#!/usr/bin/env python3
import socket, paramiko, sys, json
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
PASSWORD = "8897870998s@SS"
REMOTE = r'''
import json, urllib.request, http.cookiejar
from pathlib import Path
ROOT = Path("/opt/telegramforward.old")
pw = next(l.split("=",1)[1].strip().strip('"') for l in (ROOT/".env").read_text().splitlines() if l.startswith("DASHBOARD_PASSWORD="))
cj = http.cookiejar.CookieJar()
op = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))
op.open(urllib.request.Request("http://127.0.0.1:8000/auth/login", json.dumps({"username":"admin","password":pw}).encode(),
    headers={"Content-Type":"application/json"}, method="POST"))
with op.open(urllib.request.Request("http://127.0.0.1:8000/state"), timeout=30) as r:
    st = json.loads(r.read().decode())
for slot in ["account3","account5","account7","account8","account10","account6"]:
    a = st["account_states"].get(slot,{})
    logs = a.get("logs") or []
    print(f"\n{slot}: status={a.get('status')} groups={len(a.get('my_groups') or [])} sent={a.get('success')} fail={a.get('failed')} cycle={a.get('cycle')} notif={str(a.get('notification') or '')[:80]}")
    for lg in logs:
        s = lg if isinstance(lg,str) else str(lg.get("msg") or lg.get("message") or lg)
        if any(k in s.upper() for k in ["CYCLE_START", "SEND", "FAIL", "ERROR", "EMPTY", "HEALTH", "GROUP", "appledeveloper"]):
            print(f"  {s[:180]}")
'''
sock = socket.create_connection(("187.127.169.159", 22), timeout=30)
c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(hostname="187.127.169.159", username="root", password=PASSWORD, sock=sock)
_, stdout, _ = c.exec_command(f"cd /opt/telegramforward.old && PYTHONPATH=. ./venv/bin/python - <<'PY'\n{REMOTE}\nPY", timeout=60)
print(stdout.read().decode())
c.close()
