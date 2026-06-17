import os
import paramiko

PWD = os.environ.get("VPS_PASSWORD", "")
c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect("187.127.169.159", username="root", password=PWD, timeout=30)
cmds = [
    "grep -n 'crm-inbox-toolbar' /opt/telegramforward/dashboard/src/teleautomation-app.jsx | head -20",
    "grep -n 'crm-inbox-toolbar\\|inbox-chat-header\\|call-analytics' /opt/telegramforward/dashboard/src/index.css | head -40",
]
for cmd in cmds:
    print(">>>", cmd)
    _, o, _ = c.exec_command(cmd, timeout=60)
    print(o.read().decode("utf-8", errors="replace")[:3000])
c.close()
