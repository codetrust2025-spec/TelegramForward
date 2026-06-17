"""Fix backend import crash and PM2 cwd."""
import os
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import paramiko

PWD = os.environ.get("VPS_PASSWORD", "")
REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REMOTE = "/opt/telegramforward"
c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect("187.127.169.159", username="root", password=PWD, timeout=30)

sftp = c.open_sftp()
for rel in ["core/message_rewrite.py", "core/config.py", "server.py"]:
    local = os.path.join(REPO, rel.replace("/", os.sep))
    remote = f"{REMOTE}/{rel}"
    sftp.put(local, remote)
    print("uploaded", rel)
sftp.close()

cmds = [
    f"ls -la {REMOTE}",
    f"cd {REMOTE} && PYTHONPATH={REMOTE} ./venv/bin/python -c 'import server; print(\"ok\")'",
    "pm2 delete telegram-backend 2>/dev/null; true",
    f"cd {REMOTE} && PYTHONPATH={REMOTE} NO_RELOAD=1 pm2 start ./venv/bin/python --name telegram-backend --cwd {REMOTE} -- scripts/uvicorn_reload.py --host 0.0.0.0 --port 8000",
    "sleep 4",
    "pm2 status",
    'curl -s http://127.0.0.1:8000/health',
    "pm2 save",
]
for cmd in cmds:
    print(">>>", cmd)
    _, o, e = c.exec_command(cmd, timeout=90)
    print((o.read() + e.read()).decode("utf-8", errors="replace"))
c.close()
