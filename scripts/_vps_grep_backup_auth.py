import os
import paramiko

PWD = os.environ.get("VPS_PASSWORD", "")
c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect("187.127.169.159", username="root", password=PWD, timeout=30)
_, o, _ = c.exec_command(
    "grep -rn 'auth/login\\|DashboardAuth\\|verify.admin' /opt/telegramforward.old/_ai_deploy_backup_20260525_234049 2>/dev/null | head -20"
)
print(o.read().decode() or "(none)")
c.close()
