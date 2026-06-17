import os
import paramiko

PWD = os.environ.get("VPS_PASSWORD", "")
REMOTE = "/opt/telegramforward"
c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect("187.127.169.159", username="root", password=PWD, timeout=30)
cmds = [
    f"grep -n 'isForwardingMode\\|postingMode\\|PostingModePanel' {REMOTE}/dashboard/src/teleautomation-app.jsx | head -20",
    f"grep -n '\\bst\\b' {REMOTE}/dashboard/src/teleautomation-app.jsx | head -5",
    "grep -n 'isForwardingMode' /opt/telegramforward.old/dashboard/src/teleautomation-app.jsx | head -5",
]
for cmd in cmds:
    print("===", cmd[:100])
    _, o, _ = c.exec_command(cmd, timeout=120)
    print(o.read().decode("utf-8", errors="replace")[:3000])
c.close()
