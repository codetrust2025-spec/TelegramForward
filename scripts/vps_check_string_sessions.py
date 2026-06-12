#!/usr/bin/env python3
import os, socket, sys
import paramiko
HOST, USER = "187.127.169.159", "root"
PWD = os.environ.get("VPS_PASSWORD", "")
sock = socket.create_connection((HOST, 22), timeout=30)
c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(HOST, username=USER, password=PWD, sock=sock)
_, o, _ = c.exec_command(
    "cd /opt/telegramforward.old && source venv/bin/activate && python3 - <<'PY'\n"
    "import os\nfrom pathlib import Path\n"
    "from telethon import TelegramClient\nfrom telethon.sessions import StringSession\n"
    "from core.config import API_ID, API_HASH\n"
    "root = Path('data/accounts')\n"
    "for i in range(1, 11):\n"
    "    slot = f'account{i}'\n"
    "    p = root / slot / 'inbox_string_session.txt'\n"
    "    has = p.exists() and p.stat().st_size > 20\n"
    "    ok = False\n"
    "    err = None\n"
    "    if has:\n"
    "        s = p.read_text().strip()\n"
    "        try:\n"
    "            c = TelegramClient(StringSession(s), API_ID, API_HASH)\n"
    "            ok = True\n"
    "        except Exception as e:\n"
    "            err = str(e)[:80]\n"
    "    print(f'{slot}: string_file={has} string_client_init={ok} err={err}')\n"
    "PY",
    timeout=90,
)
print(o.read().decode())
_, o2, _ = c.exec_command("pip show telethon | grep -i version", timeout=20)
print(o2.read().decode())
c.close()
