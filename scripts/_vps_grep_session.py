import os
import paramiko

PWD = os.environ.get("VPS_PASSWORD", "")
c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect("187.127.169.159", username="root", password=PWD, timeout=30)
_, o, _ = c.exec_command(
    "grep -rn 'ta_session\\|SESSION_COOKIE\\|401\\|auth_enabled' /opt/telegramforward.old/server.py /opt/telegramforward.old/run.py 2>/dev/null"
)
print(o.read().decode() or "(none in server)")
_, o, _ = c.exec_command(
    "grep -rn 'ta_session\\|DashboardAuth\\|auth_enabled' /opt/telegramforward.old --include='*.py' 2>/dev/null | grep -v venv | head -25"
)
print(o.read().decode())
c.close()
