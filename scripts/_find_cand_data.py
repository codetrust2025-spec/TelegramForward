import os
import paramiko

HOST, USER, PASSWORD = "187.127.169.159", "root", os.environ.get("VPS_PASSWORD", "")

cmds = [
    "find /opt -name candidates.json 2>/dev/null",
    "wc -c /opt/telegramforward/data/candidates.json /opt/telegramforward.old/data/candidates.json 2>/dev/null",
    "grep POSTGRES /opt/telegramforward/.env 2>/dev/null | cut -d= -f1",
    "ls -la /opt/telegramforward/data/ 2>/dev/null | head -25",
]

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(HOST, username=USER, password=PASSWORD, timeout=30)
for cmd in cmds:
    print(">>>", cmd)
    _, o, e = c.exec_command(cmd, timeout=30)
    print(o.read().decode() or e.read().decode())
c.close()
