import os
import paramiko

PWD = os.environ.get("VPS_PASSWORD", "")
c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect("187.127.169.159", username="root", password=PWD, timeout=30)
_, o, _ = c.exec_command("cat /opt/telegramforward/core/dashboard_auth.py")
open(r"C:\Users\codet\TelegramForward\core\dashboard_auth_vps.py", "w", encoding="utf-8").write(o.read().decode())
_, o, _ = c.exec_command("grep -n 'dashboard_auth\\|verify-admin\\|auth' /opt/telegramforward/server.py | head -30")
print(o.read().decode())
c.close()
print("saved dashboard_auth_vps.py")
