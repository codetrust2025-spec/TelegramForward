import os
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
import paramiko

PWD = os.environ.get("VPS_PASSWORD", "")
c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect("187.127.169.159", username="root", password=PWD, timeout=30)

# Find richest data-room bundle source on VPS
cmds = [
    "ls -la /opt/telegramforward/static/assets/app-*.js | tail -5",
    "grep -l 'dr-vault-block' /opt/telegramforward/static/assets/*.js 2>/dev/null | head -3",
    "grep -l 'Business opportunities' /opt/telegramforward/dashboard/src -r 2>/dev/null",
    "grep -l 'dr-vault-block' /opt/telegramforward/dashboard/src -r 2>/dev/null",
    "ls -la /opt/telegramforward/static/index.html",
]
for cmd in cmds:
    print(">>>", cmd)
    _, o, _ = c.exec_command(cmd)
    print(o.read().decode("utf-8", "replace")[:2000])
c.close()
