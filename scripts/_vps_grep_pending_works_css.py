import os
import paramiko

PWD = os.environ.get("VPS_PASSWORD", "")
c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect("187.127.169.159", username="root", password=PWD, timeout=30)
cmds = [
    "grep -rni pending-works /opt/telegramforward/dashboard 2>/dev/null | head -20",
    "grep -rni 'pending work' /opt/telegramforward/dashboard/src 2>/dev/null | head -20",
    "grep -ni handler-workspace /opt/telegramforward/dashboard/src/index.css 2>/dev/null | head -15",
    "grep -ni handler-workspace /opt/telegramforward/static/assets/app-sjsEbgmN.js 2>/dev/null | head -5",
]
for cmd in cmds:
    print("===", cmd, "===")
    _, o, _ = c.exec_command(cmd)
    print(o.read().decode("utf-8", "replace")[:2000] or "(none)")
c.close()
