#!/usr/bin/env python3
"""Verify SQLite session auth for all active accounts on VPS."""
from __future__ import annotations

import os
import socket
import sys

import paramiko

HOST, USER = "187.127.169.159", "root"
PWD = os.environ.get("VPS_PASSWORD", "")

REMOTE_PY = r'''
import asyncio, sys
sys.path.insert(0, "/opt/telegramforward.old")
from core.config import ACCOUNTS, API_ID, API_HASH
from core.account_info_store import load_account_info
from core.dm_string_session import load_string_session
from telethon import TelegramClient

ACTIVE = [f"account{i}" for i in range(1, 11)]

async def check(slot):
    info = load_account_info(slot) or {}
    phone = info.get("phone")
    has_string = bool(load_string_session(slot))
    try:
        c = TelegramClient(ACCOUNTS[slot], API_ID, API_HASH)
        await c.connect()
        ok = await c.is_user_authorized()
        me = await c.get_me() if ok else None
        await c.disconnect()
        who = getattr(me, "phone", None) or getattr(me, "username", None) if me else None
        return phone, has_string, ok, who, None
    except Exception as e:
        return phone, has_string, False, None, str(e)[:80]

async def main():
    for slot in ACTIVE:
        if slot not in ACCOUNTS:
            continue
        phone, hs, ok, who, err = await check(slot)
        flag = "OK" if ok else "NEEDS OTP"
        print(f"{slot}: meta_phone={phone} string_backup={hs} session={flag} telegram={who} err={err}")

asyncio.run(main())
'''


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sock = socket.create_connection((HOST, 22), timeout=30)
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(HOST, username=USER, password=PWD, sock=sock)
    sftp = c.open_sftp()
    with sftp.file("/tmp/verify_sessions.py", "w") as f:
        f.write(REMOTE_PY)
    sftp.close()
    _, stdout, stderr = c.exec_command(
        "cd /opt/telegramforward.old && source venv/bin/activate && python3 /tmp/verify_sessions.py",
        timeout=120,
    )
    print(stdout.read().decode())
    err = stderr.read().decode().strip()
    if err:
        print("STDERR:", err[-1500:])
    c.close()


if __name__ == "__main__":
    main()
