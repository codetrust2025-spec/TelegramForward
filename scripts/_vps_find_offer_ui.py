import os
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
import paramiko

PWD = os.environ.get("VPS_PASSWORD", "")
c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect("187.127.169.159", username="root", password=PWD, timeout=30)
cmds = [
    'grep -rl "Offer letters" /opt/telegramforward/dashboard/src 2>/dev/null',
    'grep -rl "offer_letters" /opt/telegramforward/dashboard/src 2>/dev/null',
    'grep -n "vault" /opt/telegramforward/server.py 2>/dev/null | head -40',
    'wc -l /opt/telegramforward/dashboard/src/components/DataRoomPanel.jsx',
]
for cmd in cmds:
    print(">>>", cmd)
    _, o, _ = c.exec_command(cmd)
    print(o.read().decode("utf-8", "replace"))
c.close()
