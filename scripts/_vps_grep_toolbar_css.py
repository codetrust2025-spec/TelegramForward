import os
import paramiko

PWD = os.environ.get("VPS_PASSWORD", "")
c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect("187.127.169.159", username="root", password=PWD, timeout=30)
_, o, _ = c.exec_command(
    "grep -n 'chat-open\\|wa-chat-header\\|call-analytics\\|crm-inbox-toolbar' "
    "/opt/telegramforward/dashboard/src/index.css",
    timeout=60,
)
print(o.read().decode("utf-8", errors="replace"))
c.close()
