#!/usr/bin/env python3
import socket, paramiko, sys
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
PASSWORD = "REMOVED_VPS_PASSWORD"
sock = socket.create_connection(("187.127.169.159", 22), timeout=30)
c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(hostname="187.127.169.159", username="root", password=PASSWORD, sock=sock)
_, stdout, _ = c.exec_command("python3 - <<'PY'\nimport json\np='/opt/telegramforward.old/data/accounts/account10/group_intelligence.json'\nd=json.load(open(p))\nprint(list(d.keys())[:20])\nfor k in d:\n    if 'health' in k.lower() or k in ('meta','account','stats','summary'):\n        print(k, d[k])\nPY", timeout=30)
print(stdout.read().decode()[:4000])
c.close()
