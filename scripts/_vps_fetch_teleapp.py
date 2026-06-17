import os
import paramiko

PWD = os.environ.get("VPS_PASSWORD", "")
c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect("187.127.169.159", username="root", password=PWD, timeout=30)
_, o, _ = c.exec_command(
    "grep -n 'error\\|fetchCrm\\|crm/state\\|InboxPanel' "
    "/opt/telegramforward/dashboard/src/teleautomation-app.jsx 2>/dev/null | head -40",
    timeout=30,
)
print(o.read().decode("utf-8", errors="replace"))
c.close()
