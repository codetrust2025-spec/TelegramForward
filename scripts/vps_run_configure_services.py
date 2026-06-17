#!/usr/bin/env python3
import os, socket, paramiko, sys
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

PASSWORD = os.environ.get("VPS_PASSWORD", "")
LOCAL = r"C:\Users\codet\OneDrive\Desktop\Automation\scripts\configure_profile_services.py"
REMOTE = "/opt/telegramforward.old/scripts/configure_profile_services.py"

sock = socket.create_connection(("187.127.169.159", 22), timeout=30)
c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(hostname="187.127.169.159", username="root", password=PASSWORD, sock=sock)
sftp = c.open_sftp()
try:
    sftp.mkdir("/opt/telegramforward.old/scripts")
except Exception:
    pass
sftp.put(LOCAL, REMOTE)
sftp.close()

cmd = (
    "cd /opt/telegramforward.old && "
    "set -a && . ./.env && set +a && "
    "PYTHONPATH=. ./venv/bin/python scripts/configure_profile_services.py"
)
_, stdout, stderr = c.exec_command(cmd, timeout=600)
print(stdout.read().decode(errors="replace"))
err = stderr.read().decode(errors="replace")
if err.strip():
    print("STDERR:", err)
c.close()
print("Done")
