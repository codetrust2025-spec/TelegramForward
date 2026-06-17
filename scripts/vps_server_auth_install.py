#!/usr/bin/env python3
import os
import paramiko
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
PASSWORD = os.environ.get("VPS_PASSWORD", "")
c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect("187.127.169.159", username="root", password=PASSWORD, timeout=30)
cmds = [
    "readlink -f /opt/telegramforward",
    "grep -n 'install_dashboard_auth\\|dashboard_auth_api' /opt/telegramforward/server.py | head -20",
    "grep -n 'install_dashboard_auth\\|dashboard_auth_api' /opt/telegramforward.old/server.py | head -20",
    "tail -80 /opt/telegramforward/server.py",
    "python3 -c \"import sys; sys.path.insert(0,'/opt/telegramforward'); import server; print([r.path for r in server.app.routes if 'auth' in getattr(r,'path','')][:20])\" 2>&1 | head -5",
]
for cmd in cmds:
    print(f"\n=== {cmd} ===")
    _, stdout, _ = c.exec_command(cmd, timeout=45)
    print(stdout.read().decode()[:5000])
c.close()
