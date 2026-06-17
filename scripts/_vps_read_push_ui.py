import os
import paramiko

PWD = os.environ.get("VPS_PASSWORD", "")
c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect("187.127.169.159", username="root", password=PWD, timeout=30)
_, o, _ = c.exec_command(
    "grep -n 'push/vapid\\|push/subscribe' /opt/telegramforward.old/server.py; "
    "sed -n '31840,31940p' /opt/telegramforward.old/dashboard/src/teleautomation-app.jsx",
    timeout=60,
)
print(o.read().decode("utf-8", errors="replace")[:4000])
c.close()
