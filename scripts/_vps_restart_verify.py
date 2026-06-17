import os
import sys

import paramiko

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect("187.127.169.159", username="root", password=os.environ.get("VPS_PASSWORD", ""), timeout=30)
cmds = [
    "cd /opt/telegramforward && PYTHONPATH=/opt/telegramforward pm2 restart telegram-backend --update-env",
    "sleep 2",
    "curl -s http://127.0.0.1:8000/health",
    "curl -s -o /dev/null -w 'inbox:%{http_code}\\n' 'http://127.0.0.1:8000/inbox?sync=0'",
    "PYTHONPATH=/opt/telegramforward /opt/telegramforward/venv/bin/python -c \"from core.config import is_whatsapp_enabled; print('whatsapp', is_whatsapp_enabled())\"",
]
for cmd in cmds:
    _, o, e = c.exec_command(cmd, timeout=120)
    print(">>>", cmd[:70])
    out = o.read().decode()
    if out:
        print(out)
    err = e.read().decode().strip()
    if err:
        print("stderr:", err[:200])
c.close()
