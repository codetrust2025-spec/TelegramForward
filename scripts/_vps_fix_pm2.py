"""Fix PM2 to run /opt/telegramforward and restart backend."""
import os
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import paramiko

PWD = os.environ.get("VPS_PASSWORD", "")
REMOTE = "/opt/telegramforward"
c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect("187.127.169.159", username="root", password=PWD, timeout=30)

cmds = [
    "pm2 describe telegram-backend 2>&1 | head -40",
    f"cd {REMOTE} && ./venv/bin/python -c 'import server; print(\"server ok\")' 2>&1",
    f"pm2 delete telegram-backend 2>/dev/null; cd {REMOTE} && pm2 start ./venv/bin/python --name telegram-backend -- scripts/uvicorn_reload.py --host 0.0.0.0 --port 8000",
    "sleep 3",
    "pm2 status",
    f'curl -s http://127.0.0.1:8000/health',
]
for cmd in cmds:
    print(">>>", cmd)
    _, o, e = c.exec_command(cmd, timeout=90)
    print((o.read() + e.read()).decode("utf-8", errors="replace"))
c.close()
