#!/usr/bin/env python3
import os, socket, paramiko, sys
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
PASSWORD = os.environ.get("VPS_PASSWORD", "")
sock = socket.create_connection(("187.127.169.159", 22), timeout=30)
c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(hostname="187.127.169.159", username="root", password=PASSWORD, sock=sock)
cmds = [
    "pm2 show telegram-backend | grep -E 'script path|interpreter|exec cwd'",
    "cat /root/.pm2/dump.pm2 2>/dev/null | python3 -c \"import sys,json; d=json.load(sys.stdin); print([x for x in d if x.get('name')=='telegram-backend'][0].get('pm_exec_path',''), [x for x in d if x.get('name')=='telegram-backend'][0].get('pm_cwd',''), [x for x in d if x.get('name')=='telegram-backend'][0].get('interpreter',''))\" 2>/dev/null || pm2 jlist | python3 -c \"import sys,json; apps=json.load(sys.stdin); a=[x for x in apps if x.get('name')=='telegram-backend'][0]; print(a.get('pm_exec_path'), a.get('pm_cwd'), a.get('interpreter'))\"",
    "ls /opt/telegramforward.old/.venv/bin/python 2>/dev/null; ls /opt/telegramforward.old/venv/bin/python 2>/dev/null; which python3",
]
for cmd in cmds:
    print("\n---", cmd[:70])
    _, stdout, _ = c.exec_command(cmd, timeout=30)
    print(stdout.read().decode(errors="replace"))
c.close()
