import os
import paramiko

PWD = os.environ.get("VPS_PASSWORD", "")
c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect("187.127.169.159", username="root", password=PWD, timeout=30)
cmds = [
    "grep -rn 'vapid-public\\|push/subscribe' /opt/telegramforward.old /opt/telegramforward 2>/dev/null | head -25",
    "sed -n '111,175p' /opt/telegramforward.old/features/web_push.py",
]
for cmd in cmds:
    print("===", cmd)
    _, o, _ = c.exec_command(cmd, timeout=60)
    print(o.read().decode())
c.close()
