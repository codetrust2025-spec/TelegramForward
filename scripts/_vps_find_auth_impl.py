import os
import paramiko

PWD = os.environ.get("VPS_PASSWORD", "")
c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect("187.127.169.159", username="root", password=PWD, timeout=30)
_, o, _ = c.exec_command(
    "grep -rn 'def.*login\\|auth/login\\|register.*auth' /opt/telegramforward.old/core /opt/telegramforward.old/features 2>/dev/null | head -30"
)
print(o.read().decode())
_, o, _ = c.exec_command("wc -l /opt/telegramforward.old/core/admin_dashboard.py 2>/dev/null; grep -n auth /opt/telegramforward.old/core/admin_dashboard.py 2>/dev/null | head -20")
print(o.read().decode())
c.close()
