#!/usr/bin/env python3
"""Cold session recovery — no OTP. Clears stale Telethon connections and lock files."""
from __future__ import annotations

import os
import socket
import sys
import time

import paramiko

HOST, USER = "187.127.169.159", "root"
PWD = os.environ.get("VPS_PASSWORD", "")
REMOTE_ROOT = "/opt/telegramforward.old"
ACTIVE = [f"account{i}" for i in range(1, 11)]

REMOTE_PY = f'''
import asyncio, glob, json, os, subprocess, sys, time, urllib.request
sys.path.insert(0, "{REMOTE_ROOT}")

from core.config import ACCOUNTS
from core.dashboard_auth_vps import get_credentials, create_session_token, SESSION_COOKIE
from core.daily_stats import compute_daily_stats

ACTIVE = {ACTIVE!r}

user, _ = get_credentials()
token = create_session_token(user, role="admin")

def api(method, path, timeout=20):
    req = urllib.request.Request(
        "http://127.0.0.1:8000" + path,
        method=method,
        data=b"" if method == "POST" else None,
    )
    req.add_header("Cookie", f"{{SESSION_COOKIE}}={{token}}")
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode())

async def release_all():
    from core import telegram_client
    from core.session_manager import session_manager
    for slot in ACTIVE:
        if slot not in ACCOUNTS:
            continue
        try:
            await session_manager.release(slot, wait=0.2)
        except Exception as e:
            print(f"  release {{slot}}: {{e}}")
    try:
        await telegram_client.abandon_all_sessions()
    except Exception as e:
        print(f"  abandon_all: {{e}}")

print("=== Stop all ===")
try:
    print(api("POST", "/stop", timeout=45))
except Exception as e:
    print("stop:", e)

print("\\n=== Release sessions ===")
asyncio.run(release_all())

print("\\n=== Clear lock sidecars (keep .session) ===")
for pattern in [
    "{REMOTE_ROOT}/session_*.session-journal",
    "{REMOTE_ROOT}/session_*.session-wal",
    "{REMOTE_ROOT}/session_*.session-shm",
]:
    for path in glob.glob(pattern):
        try:
            os.remove(path)
            print(" removed", os.path.basename(path))
        except OSError as e:
            print(" skip", path, e)

print("\\n=== pm2 restart backend ===")
subprocess.run(["pm2", "restart", "telegram-backend"], check=False)
time.sleep(8)

print("\\n=== Validate sessions (no OTP) ===")
async def validate():
    from core.session_manager import session_manager
    ok, bad = [], []
    for slot in ACTIVE:
        if slot not in ACCOUNTS:
            continue
        try:
            if await session_manager.validate_session(slot):
                ok.append(slot)
            else:
                bad.append(slot)
        except Exception:
            bad.append(slot)
        await asyncio.sleep(0.5)
    return ok, bad

ok, bad = asyncio.run(validate())
print("OK:", ", ".join(ok) if ok else "(none)")
print("NEED OTP:", ", ".join(bad) if bad else "(none)")

print("\\n=== Start all ===")
try:
    print(api("POST", "/start", timeout=15))
except Exception as e:
    print("start:", e)
time.sleep(20)

ds = compute_daily_stats([s for s in ACTIVE if s in ACCOUNTS])
g = ds.get("global") or {{}}
print("\\nPosts today:", "fwd=", g.get("forward_posts"), "camp=", g.get("campaign_posts"))

r = subprocess.run(
    ["bash", "-lc", "grep -c 'wrong session' /root/.pm2/logs/telegram-backend-error.log 2>/dev/null || echo 0"],
    capture_output=True, text=True, timeout=15,
)
print("wrong_session_errors_in_log:", (r.stdout or "").strip())
print("DONE")
'''


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sock = socket.create_connection((HOST, 22), timeout=30)
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(HOST, username=USER, password=PWD, sock=sock)
    sftp = c.open_sftp()
    with sftp.file("/tmp/session_cold_recovery.py", "w") as f:
        f.write(REMOTE_PY)
    sftp.close()
    print("Running cold session recovery on VPS (no OTP)...")
    _, stdout, stderr = c.exec_command(
        f"cd {REMOTE_ROOT} && source venv/bin/activate && python3 /tmp/session_cold_recovery.py",
        timeout=180,
    )
    print(stdout.read().decode())
    err = stderr.read().decode().strip()
    if err:
        print("STDERR:", err)
    c.close()


if __name__ == "__main__":
    main()
