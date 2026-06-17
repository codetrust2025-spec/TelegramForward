import os
import paramiko

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect("187.127.169.159", username="root", password=os.environ.get("VPS_PASSWORD", ""), timeout=30)
_, o, _ = c.exec_command("tail -40 /root/.pm2/logs/telegram-backend-out.log", timeout=15)
print(o.read().decode())
c.close()
