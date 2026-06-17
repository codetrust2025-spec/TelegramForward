import os
import paramiko

PWD = os.environ.get("VPS_PASSWORD", "")
c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect("187.127.169.159", username="root", password=PWD, timeout=30)
cmds = [
    "grep -rn 'verify-admin\\|/auth/login' /opt/telegramforward.old --include='*.py' 2>/dev/null | grep -v venv | head -20",
    "grep DASHBOARD_PASSWORD /opt/telegramforward.old/.env 2>/dev/null || grep DASHBOARD_PASSWORD /opt/telegramforward/.env",
    "cat /opt/telegramforward.old/.env 2>/dev/null | grep PASSWORD",
]
for cmd in cmds:
    print(">>>", cmd)
    _, o, _ = c.exec_command(cmd)
    print(o.read().decode())
c.close()
