import os
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
import paramiko

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect("187.127.169.159", "root", password=os.environ.get("VPS_PASSWORD", ""), timeout=30)
cmds = [
    "pm2 status",
    "pm2 logs telegram-backend --lines 50 --nostream 2>&1",
    "curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1:8000/health",
    "curl -s -o /dev/null -w '%{http_code}' 'http://127.0.0.1:8000/admin/dashboard?window_hours=24'",
    "grep -n 'def install_admin' /opt/telegramforward.old/core/admin_dashboard.py",
    "tail -5 /opt/telegramforward.old/server.py",
]
for cmd in cmds:
    print("===", cmd)
    _, o, _ = c.exec_command(cmd, timeout=90)
    print(o.read().decode("utf-8", errors="replace")[:3000])
c.close()
