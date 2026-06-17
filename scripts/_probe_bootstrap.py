import os
import paramiko

PWD = os.environ["VPS_PASSWORD"]
c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect("187.127.169.159", username="root", password=PWD, timeout=30)
cmds = [
    "grep -n 'candidates/bootstrap' /opt/telegramforward.old/server.py /opt/telegramforward/server.py 2>/dev/null | head -10",
    "stat -c '%n %s' /opt/telegramforward/data/candidates.json /opt/telegramforward.old/data/candidates.json 2>&1",
    "find /opt/telegramforward -name 'candidates.json*' -size +1k 2>/dev/null | head -10",
]
for cmd in cmds:
    print("===", cmd)
    _, o, _ = c.exec_command(cmd)
    print(o.read().decode("utf-8", errors="replace"))
c.close()
