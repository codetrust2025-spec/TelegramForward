#!/usr/bin/env python3
import os, socket, sys, json
import paramiko
HOST, USER = "187.127.169.159", "root"
PWD = os.environ.get("VPS_PASSWORD", "")
sock = socket.create_connection((HOST, 22), timeout=30)
c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(HOST, username=USER, password=PWD, sock=sock)
_, o, _ = c.exec_command(
    "cd /opt/telegramforward.old && source venv/bin/activate && python3 - <<'PY'\n"
    "import json\nfrom core.config import ACCOUNTS\n"
    "print('count', len(ACCOUNTS))\n"
    "for k in ['account1','account2','account10']:\n"
    "    print(k, repr(ACCOUNTS.get(k)))\n"
    "try:\n"
    "    from telethon import TelegramClient\n"
    "    from core.config import API_ID, API_HASH\n"
    "    c = TelegramClient(ACCOUNTS['account1'], API_ID, API_HASH)\n"
    "    print('TelegramClient init OK', type(c.session))\n"
    "except Exception as e:\n"
    "    print('TelegramClient init FAIL', e)\n"
    "PY",
    timeout=60,
)
print(o.read().decode())
c.close()
