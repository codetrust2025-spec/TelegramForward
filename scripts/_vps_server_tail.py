import os
import paramiko

PWD = os.environ.get("VPS_PASSWORD", "")
c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect("187.127.169.159", username="root", password=PWD, timeout=30)
cmds = [
    "grep -n 'install_' /opt/telegramforward.old/server.py | tail -25",
    "tail -80 /opt/telegramforward.old/server.py",
]
for cmd in cmds:
    print(">>>", cmd)
    _, o, _ = c.exec_command(cmd, timeout=30)
    print(o.read().decode("utf-8", errors="replace"))
c.close()
