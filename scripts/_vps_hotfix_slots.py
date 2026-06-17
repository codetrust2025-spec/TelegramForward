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
for rel in ["core/config.py", "server.py"]:
    sftp.put(os.path.join(REPO, rel.replace("/", os.sep)), f"{REMOTE}/{rel}")
    print("uploaded", rel)
sftp.close()
cmds = [
    f"cd {REMOTE} && PYTHONPATH={REMOTE} ./venv/bin/python -c \"from core.config import reload_accounts; reload_accounts(); import core.config as c; print('slots', c.ACCOUNT_SLOTS)\"",
    "pm2 restart telegram-backend --update-env",
    "sleep 4",
    "pm2 status",
    'curl -s http://127.0.0.1:8000/health',
]
for cmd in cmds:
    print(">>>", cmd)
    _, o, e = c.exec_command(cmd, timeout=60)
    print((o.read() + e.read()).decode("utf-8", errors="replace"))
c.close()
