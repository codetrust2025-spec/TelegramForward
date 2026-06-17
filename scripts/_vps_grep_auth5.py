import os
import paramiko

PWD = os.environ.get("VPS_PASSWORD", "")
c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect("187.127.169.159", username="root", password=PWD, timeout=30)
_, o, _ = c.exec_command("pm2 show telegram-backend 2>/dev/null | head -40")
print(o.read().decode())
_, o, _ = c.exec_command("head -5 /opt/telegramforward.old/scripts/uvicorn_reload.py 2>/dev/null; grep -rn 'auth' /opt/telegramforward.old/server.py 2>/dev/null | head -15")
print(o.read().decode())
c.close()
