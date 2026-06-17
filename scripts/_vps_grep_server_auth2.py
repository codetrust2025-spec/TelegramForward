import os
import paramiko

PWD = os.environ.get("VPS_PASSWORD", "")
c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect("187.127.169.159", username="root", password=PWD, timeout=30)
for pat in ["/auth/login", "auth/login", "DashboardAuth", "verify-admin"]:
    _, o, _ = c.exec_command(f"grep -rn '{pat}' /opt/telegramforward --include='*.py' 2>/dev/null | grep -v venv | head -20")
    print(f"--- {pat} ---")
    print(o.read().decode() or "(none)")
c.close()
