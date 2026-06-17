import os
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
import paramiko

REMOTE = "/opt/telegramforward.old"
c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect("187.127.169.159", "root", password=os.environ.get("VPS_PASSWORD", ""), timeout=30)
cmds = [
    "pm2 logs telegram-backend --lines 35 --nostream 2>&1",
    f"grep -n 'def install' {REMOTE}/core/admin_dashboard.py",
    f"tail -30 {REMOTE}/core/admin_dashboard.py",
    f"sed -n '50,65p' {REMOTE}/server.py",
]
for cmd in cmds:
    print("===", cmd[:90])
    _, o, _ = c.exec_command(cmd, timeout=90)
    print(o.read().decode("utf-8", errors="replace")[:3500])
c.close()
