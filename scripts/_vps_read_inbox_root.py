import os
import paramiko

PWD = os.environ.get("VPS_PASSWORD", "")
c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect("187.127.169.159", username="root", password=PWD, timeout=30)
_, o, _ = c.exec_command(
    "grep -o '.inbox-root[^;]*' /opt/telegramforward/dashboard/src/teleautomation-app.jsx | head -3",
    timeout=60,
)
print(o.read().decode("utf-8", errors="replace"))
# extract call-analytics placement
_, o, _ = c.exec_command(
    "grep -o 'crm-inbox-toolbar[^<]*<[^/]*' /opt/telegramforward/dashboard/src/teleautomation-app.jsx | head -1",
    timeout=60,
)
print(o.read().decode("utf-8", errors="replace")[:500])
c.close()
