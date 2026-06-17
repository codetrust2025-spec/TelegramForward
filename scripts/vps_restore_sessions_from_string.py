#!/usr/bin/env python3
"""Rebuild corrupted SQLite sessions from saved string sessions — no OTP for most accounts."""
from __future__ import annotations

import os
import socket
import sys
import time

import paramiko

HOST, USER = "187.127.169.159", "root"
PWD = os.environ.get("VPS_PASSWORD", "")
REMOTE = "/opt/telegramforward.old"
ACTIVE = [f"account{i}" for i in range(1, 11)]

REMOTE_PY = f'''
import asyncio, json, subprocess, sys, time, urllib.request
from pathlib import Path
sys.path.insert(0, "{REMOTE}")

from core.config import ACCOUNTS, API_ID, API_HASH
from core.dashboard_auth_vps import get_credentials, create_session_token, SESSION_COOKIE
from core.daily_stats import compute_daily_stats
from core.dm_string_session import load_string_session
from core.telegram_client import _main_session_base, _write_sqlite_session_from_string
from telethon import TelegramClient

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

from telethon.sessions import StringSession

async def test_auth(slot, session_str):
    client = TelegramClient(StringSession(session_str), API_ID, API_HASH)
    await client.connect()
    ok = await client.is_user_authorized()
    me = await client.get_me() if ok else None
    await client.disconnect()
    return ok, getattr(me, "phone", None) or getattr(me, "username", None)

async def run_restore():
    restored, need_otp = [], []
    for slot in ACTIVE:
        if slot not in ACCOUNTS:
            continue
        s = load_string_session(slot)
        if not s:
            print(f"{{slot}}: NO string backup — needs OTP login")
            need_otp.append(slot)
            continue
        try:
            ok, who = await test_auth(slot, s)
            if not ok:
                print(f"{{slot}}: string session not authorized — needs OTP")
                need_otp.append(slot)
                continue
            base = _main_session_base(slot)
            _write_sqlite_session_from_string(s, base)
            client = TelegramClient(ACCOUNTS[slot], API_ID, API_HASH)
            await client.connect()
            ok2 = await client.is_user_authorized()
            await client.disconnect()
            print(f"{{slot}}: RESTORED from string ({{who}}) sqlite_ok={{ok2}}")
            if ok2:
                restored.append(slot)
            else:
                need_otp.append(slot)
        except Exception as e:
            print(f"{{slot}}: restore FAILED — {{e}}")
            need_otp.append(slot)
    return restored, need_otp

print("=== Rebuild SQLite sessions from string backups ===")
restored, need_otp = asyncio.run(run_restore())

print("\\n=== Restart backend + start fleet ===")
subprocess.run(["pm2", "restart", "telegram-backend"], check=False)
time.sleep(8)
try:
    print(api("POST", "/start", timeout=15))
except Exception as e:
    print("start:", e)
time.sleep(25)

ds = compute_daily_stats([s for s in ACTIVE if s in ACCOUNTS])
g = ds.get("global") or {{}}
print("\\nPosts today: fwd=", g.get("forward_posts"), "camp=", g.get("campaign_posts"))
print("\\nRestored (no OTP):", ", ".join(restored) or "none")
print("Still need OTP:", ", ".join(need_otp) or "none")
print("DONE")
'''


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sock = socket.create_connection((HOST, 22), timeout=30)
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(HOST, username=USER, password=PWD, sock=sock)
    sftp = c.open_sftp()
    with sftp.file("/tmp/restore_string_sessions.py", "w") as f:
        f.write(REMOTE_PY)
    sftp.close()
    print("Restoring sessions from string backups (no OTP)...")
    _, stdout, stderr = c.exec_command(
        f"cd {REMOTE} && source venv/bin/activate && python3 /tmp/restore_string_sessions.py",
        timeout=300,
    )
    print(stdout.read().decode())
    err = stderr.read().decode().strip()
    if err:
        print("STDERR:", err[-2000:])
    c.close()


if __name__ == "__main__":
    main()
