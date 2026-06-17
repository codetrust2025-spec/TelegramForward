import os
import paramiko

PWD = os.environ.get("VPS_PASSWORD", "")
c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect("187.127.169.159", username="root", password=PWD, timeout=30)
_, o, _ = c.exec_command("sed -n '40,160p' /opt/telegramforward/dashboard/src/teleautomation-app.jsx")
open(r"C:\Users\codet\TelegramForward\ta-login.txt", "w", encoding="utf-8").write(o.read().decode())
print("ok")
c.close()
