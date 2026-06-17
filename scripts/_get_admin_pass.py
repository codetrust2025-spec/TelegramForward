import os
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
import paramiko

PWD = os.environ.get("VPS_PASSWORD", "")
c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect("187.127.169.159", username="root", password=PWD, timeout=30)
_, o, _ = c.exec_command(
    "cd /opt/telegramforward && venv/bin/python -c \"from core import dashboard_auth_vps as a; u,p=a.get_credentials(); print(u); print(p)\"",
    timeout=30,
)
print(o.read().decode())
c.close()
