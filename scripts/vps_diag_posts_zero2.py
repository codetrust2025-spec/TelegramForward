#!/usr/bin/env python3
from __future__ import annotations

import socket
import sys

import paramiko

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
PASSWORD = "8897870998s@SS"
HOST = "187.127.169.159"

def main():
    sock = socket.create_connection((HOST, 22), timeout=30)
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(hostname=HOST, username="root", password=PASSWORD, sock=sock)
    cmds = [
        "pm2 logs telegram-backend --lines 80 --nostream 2>&1 | tail -80",
        "grep -h 'Connection failed\\|get_me\\|forward tick\\|Message sent\\|forwarded to\\|Cycle error' /root/.pm2/logs/telegram-backend-out.log 2>/dev/null | tail -40",
        "python3 - <<'PY'\nfrom pathlib import Path\nimport json\nfor slot in ['account1','account2','account4','account6','account9','account3','account7']:\n    p=Path(f'/opt/telegramforward.old/data/accounts/{slot}/account_info.json')\n    if p.exists():\n        d=json.loads(p.read_text())\n        print(slot, 'logged_in', bool(d), 'phone', d.get('phone','')[:20] if d else '')\n    else:\n        print(slot, 'NO account_info.json')\nPY",
    ]
    for cmd in cmds:
        print("\n===", cmd.split()[0], "===")
        _, stdout, stderr = c.exec_command(cmd, timeout=60)
        print(stdout.read().decode('utf-8', errors='replace'))
        err = stderr.read().decode('utf-8', errors='replace')
        if err.strip():
            print('ERR', err[:500])
    c.close()

if __name__ == '__main__':
    main()
