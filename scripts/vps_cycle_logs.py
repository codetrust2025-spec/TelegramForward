#!/usr/bin/env python3
import socket, paramiko, sys
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
PASSWORD = "REMOVED_VPS_PASSWORD"
cmds = [
    "grep -n 'CYCLE_RESUME\\|get_me failed' /opt/telegramforward.old/workers/account_worker.py | head -20",
    "grep -rn 'CYCLE_RESUME' /opt/telegramforward.old --include='*.py' | head -15",
    """cd /opt/telegramforward.old && set -a && . ./.env && set +a && PYTHONPATH=. ./venv/bin/python - <<'PY'
import json, urllib.request, http.cookiejar
from pathlib import Path
ROOT = Path(".")
pw = next(l.split("=",1)[1].strip().strip('"') for l in (ROOT/".env").read_text().splitlines() if l.startswith("DASHBOARD_PASSWORD="))
cj = http.cookiejar.CookieJar()
op = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))
op.open(urllib.request.Request("http://127.0.0.1:8000/auth/login", json.dumps({"username":"admin","password":pw}).encode(),
    headers={"Content-Type":"application/json"}, method="POST"))
with op.open(urllib.request.Request("http://127.0.0.1:8000/state"), timeout=30) as r:
    st = json.loads(r.read().decode())
for slot in ["account3","account5","account7","account8","account10"]:
    a = st["account_states"].get(slot,{})
    logs = a.get("logs") or []
    print(f"\\n=== {slot} last 15 logs ===")
    for lg in logs[-15:]:
        print(lg if isinstance(lg,str) else lg.get("msg") or lg.get("message") or json.dumps(lg)[:150])
PY""",
]
sock = socket.create_connection(("187.127.169.159", 22), timeout=30)
c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(hostname="187.127.169.159", username="root", password=PASSWORD, sock=sock)
for cmd in cmds:
    print("=== CMD ===")
    _, stdout, _ = c.exec_command(cmd, timeout=90)
    print(stdout.read().decode("utf-8", errors="replace")[:12000])
c.close()
