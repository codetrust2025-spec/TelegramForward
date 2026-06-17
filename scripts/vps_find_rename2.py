#!/usr/bin/env python3
import os, socket, paramiko, sys
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
PASSWORD = os.environ.get("VPS_PASSWORD", "")
sock = socket.create_connection(("187.127.169.159", 22), timeout=30)
c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(hostname="187.127.169.159", username="root", password=PASSWORD, sock=sock)
cmds = [
    "sed -n '540,620p' /opt/telegramforward.old/server.py",
    "cat /opt/telegramforward.old/core/account_info_store.py",
    "grep -rn 'UpdateProfile\\|set_profile\\|first_name\\|display_name' /opt/telegramforward.old/core/*.py | grep -v dm_store | head -40",
    "for s in account1 account2 account3 account4 account5 account6 account7 account8 account9 account10 account11; do f=/opt/telegramforward.old/data/accounts/$s/account_info.json; if [ -f \"$f\" ]; then echo -n \"$s: \"; python3 -c \"import json; d=json.load(open('$f')); print(d.get('display_name') or d.get('name','?'))\"; fi; done",
    "ls /opt/telegramforward.old/data/accounts/account11/ 2>/dev/null | head -5",
]
for cmd in cmds:
    print("\n===", cmd[:90], "===")
    _, stdout, _ = c.exec_command(cmd, timeout=60)
    print(stdout.read().decode(errors="replace")[:8000])
c.close()
