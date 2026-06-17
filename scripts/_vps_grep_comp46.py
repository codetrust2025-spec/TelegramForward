import os
import paramiko

PWD = os.environ.get("VPS_PASSWORD", "")
c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect("187.127.169.159", username="root", password=PWD, timeout=30)
_, o, _ = c.exec_command(
    "grep -n 'function _Component46\\|_Component46' /opt/telegramforward/dashboard/src/teleautomation-app.jsx | head -8",
    timeout=30,
)
print(o.read().decode("utf-8", errors="replace"))
c.close()
