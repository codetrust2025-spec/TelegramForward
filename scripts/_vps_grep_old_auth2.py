import os
import paramiko

PWD = os.environ.get("VPS_PASSWORD", "")
c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect("187.127.169.159", username="root", password=PWD, timeout=30)
_, o, _ = c.exec_command("grep -n 'auth' /opt/telegramforward.old/server.py | head -50")
print(o.read().decode())
_, o, _ = c.exec_command("head -120 /opt/telegramforward.old/server.py")
print(o.read().decode()[:4000])
c.close()
