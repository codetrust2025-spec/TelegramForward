import os
import paramiko

PWD = os.environ.get("VPS_PASSWORD", "")
c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect("187.127.169.159", username="root", password=PWD, timeout=30)
_, o, _ = c.exec_command("grep -n '@app.*auth\\|verify' /opt/telegramforward/server.py | head -25")
print(o.read().decode())
_, o, _ = c.exec_command("grep -n 'dashboard_auth' /opt/telegramforward/server.py | head -20")
print(o.read().decode())
c.close()
