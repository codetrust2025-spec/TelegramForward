#!/usr/bin/env python3
import socket, paramiko, sys
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
PASSWORD = "REMOVED_VPS_PASSWORD"
REMOTE = r'''
import json, glob, os
from pathlib import Path
ROOT = Path("/opt/telegramforward.old")

# structured logs
print("=== STRUCTURED LOGS (recent SEND_FAIL / get_me) ===")
for slot in ["account3","account5","account7","account8","account10"]:
    for pat in [f"{ROOT}/data/logs/{slot}*.jsonl", f"{ROOT}/data/accounts/{slot}/logs*.jsonl", f"/root/.pm2/logs/*"]:
        pass
    # check log dir
log_dirs = list((ROOT/"data").rglob("*log*"))
print("log paths sample:", [str(p) for p in log_dirs[:15]])

# grep pm2 out for get_me and structured
import subprocess
for pattern in ["get_me", "SEND_FAIL", "recovering", "appledeveloper", "Error —"]:
    r = subprocess.run(["grep", "-i", pattern, "/root/.pm2/logs/telegram-backend-out.log"],
        capture_output=True, text=True, timeout=30)
    lines = r.stdout.strip().splitlines()[-15:]
    if lines:
        print(f"\n--- out.log {pattern} (last {len(lines)}) ---")
        for ln in lines:
            print(ln[:220])

r2 = subprocess.run(["grep", "-i", "get_me", "/root/.pm2/logs/telegram-backend-error.log"],
    capture_output=True, text=True, timeout=30)
if r2.stdout.strip():
    print("\n--- error.log get_me ---")
    for ln in r2.stdout.strip().splitlines()[-20:]:
        print(ln[:220])

# Test get_me for account7 directly
print("\n=== DIRECT get_me TEST account7 ===")
import asyncio
from core import telegram_client
from core.account_info_store import load_account_info

async def test(slot):
    info = load_account_info(slot)
    if not info or not info.get("phone"):
        return f"{slot}: not logged in"
    try:
        async def op(client):
            me = await client.get_me()
            return f"OK id={me.id} name={me.first_name}"
        return await telegram_client.run_dm_operation(slot, op, attach_inbox_handlers=False)
    except Exception as e:
        return f"FAIL: {type(e).__name__}: {e}"

async def main():
    for slot in ["account3","account5","account7","account8","account10"]:
        print(f"{slot}: {await test(slot)}")
        await asyncio.sleep(2)

asyncio.run(main())

# Current API state notifications
import urllib.request, http.cookiejar
pw = next(l.split("=",1)[1].strip().strip('"') for l in (ROOT/".env").read_text().splitlines() if l.startswith("DASHBOARD_PASSWORD="))
cj = http.cookiejar.CookieJar()
op = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))
op.open(urllib.request.Request("http://127.0.0.1:8000/auth/login", json.dumps({"username":"admin","password":pw}).encode(),
    headers={"Content-Type":"application/json"}, method="POST"))
with op.open(urllib.request.Request("http://127.0.0.1:8000/state"), timeout=30) as r:
    st = json.loads(r.read().decode())
for slot in ["account3","account5","account7","account8","account10"]:
    a = st["account_states"].get(slot,{})
    print(f"API {slot}: status={a.get('status')} my_groups={len(a.get('my_groups') or [])} notif={a.get('notification')}")
    logs = a.get("logs") or []
    for lg in logs[-3:]:
        if isinstance(lg, dict):
            print(f"  log: {lg.get('msg') or lg.get('message') or lg}")
        else:
            print(f"  log: {str(lg)[:120]}")
'''
sock = socket.create_connection(("187.127.169.159", 22), timeout=30)
c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(hostname="187.127.169.159", username="root", password=PASSWORD, sock=sock)
_, stdout, stderr = c.exec_command(
    f"cd /opt/telegramforward.old && set -a && . ./.env && set +a && PYTHONPATH=. ./venv/bin/python - <<'PY'\n{REMOTE}\nPY",
    timeout=180,
)
print(stdout.read().decode("utf-8", errors="replace"))
err = stderr.read().decode("utf-8", errors="replace")
if err.strip(): print("ERR:", err[-4000:])
c.close()
