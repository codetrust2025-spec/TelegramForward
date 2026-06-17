import os
import paramiko

PWD = os.environ.get("VPS_PASSWORD", "")
c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect("187.127.169.159", username="root", password=PWD, timeout=30)
_, o, _ = c.exec_command(
    "grep -rn '@app\\|auth/login\\|verify' /opt/telegramforward.old/server.py /opt/telegramforward.old/run.py 2>/dev/null | head -40"
)
print(o.read().decode())
_, o, _ = c.exec_command("grep -rn 'dashboard_auth' /opt/telegramforward.old --include='*.py' 2>/dev/null | grep -v venv | head -25")
print("imports:", o.read().decode())
c.close()
