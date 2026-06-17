import os
import paramiko

PWD = os.environ.get("VPS_PASSWORD", "")
c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect("187.127.169.159", username="root", password=PWD, timeout=30)
_, o, _ = c.exec_command(
    "find /opt/telegramforward.old /opt/telegramforward -name '*auth*' -type f 2>/dev/null | grep -v venv | grep -v __pycache__"
)
print(o.read().decode())
_, o, _ = c.exec_command(
    "grep -rn '@app.post.*auth' /opt/telegramforward.old /opt/telegramforward 2>/dev/null | grep -v venv"
)
print("routes:", o.read().decode() or "(none)")
c.close()
