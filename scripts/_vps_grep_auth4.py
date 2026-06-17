import os
import paramiko

PWD = os.environ.get("VPS_PASSWORD", "")
c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect("187.127.169.159", username="root", password=PWD, timeout=30)
_, o, _ = c.exec_command(
    "grep -rn 'dashboard_auth' /opt/telegramforward --include='*.py' 2>/dev/null | grep -v venv"
)
print(o.read().decode())
c.close()
