import os
import paramiko

PWD = os.environ.get("VPS_PASSWORD", "")
c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect("187.127.169.159", username="root", password=PWD, timeout=30)
cmds = [
    "find /opt/telegramforward.old -name '*voice*' -type f 2>/dev/null | head -20",
    "grep -rn '/voice/' /opt/telegramforward.old --include='*.py' 2>/dev/null | head -25",
    "grep -rn 'get_analytics' /opt/telegramforward.old --include='*.py' 2>/dev/null",
]
for cmd in cmds:
    print(">>>", cmd)
    _, o, _ = c.exec_command(cmd, timeout=60)
    print(o.read().decode("utf-8", errors="replace")[:2500])
c.close()
