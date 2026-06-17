import os
import paramiko

PWD = os.environ.get("VPS_PASSWORD", "")
c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect("187.127.169.159", username="root", password=PWD, timeout=30)
_, o, _ = c.exec_command("grep -rn 'verify-admin\\|verify_admin\\|/auth' /opt/telegramforward/server.py /opt/telegramforward/core /opt/telegramforward/features 2>/dev/null | head -30")
print(o.read().decode())
_, o, _ = c.exec_command("cat /opt/telegramforward/.env | grep -i password")
print("env:", o.read().decode())
c.close()
