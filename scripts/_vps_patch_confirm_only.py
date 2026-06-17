import os
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
import paramiko

PWD = os.environ.get("VPS_PASSWORD", "")
c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect("187.127.169.159", username="root", password=PWD, timeout=30)
cmd = "cd /opt/telegramforward && node scripts/_patch_confirm.js 2>&1; echo exit=$?"
_, o, _ = c.exec_command(cmd, timeout=60)
print(o.read().decode())
c.close()
