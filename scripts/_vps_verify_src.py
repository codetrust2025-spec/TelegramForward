import os
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
import paramiko

PWD = os.environ.get("VPS_PASSWORD", "")
c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect("187.127.169.159", username="root", password=PWD, timeout=30)
cmds = [
    "grep -n PostingModePanel /opt/telegramforward/dashboard/src/components/AccountCard.jsx | head -3",
    "grep -n 'Posting mode' /opt/telegramforward/dashboard/src/components/PostingModePanel.jsx | head -3",
    "wc -c /opt/telegramforward/dashboard/src/App.jsx",
    "head -3 /opt/telegramforward/dashboard/src/App.jsx",
    "grep -c TeleAutomation /opt/telegramforward/dashboard/src/App.jsx || true",
]
for cmd in cmds:
    print(">>>", cmd)
    _, o, _ = c.exec_command(cmd, timeout=30)
    print(o.read().decode("utf-8", errors="replace"))
c.close()
