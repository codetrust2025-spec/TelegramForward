import os
import paramiko

PWD = os.environ.get("VPS_PASSWORD", "")
REMOTE = "/opt/telegramforward"
c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect("187.127.169.159", username="root", password=PWD, timeout=30)
for pat in ["DASHBOARD_PASSWORD", "admin/password", "verify.*password", "candidates.*admin", "handler.*expense"]:
    cmd = f"grep -rn '{pat}' {REMOTE}/server.py {REMOTE}/features/candidate*.py 2>/dev/null | head -25"
    _, o, _ = c.exec_command(cmd, timeout=60)
    print(o.read().decode("utf-8", errors="replace")[:4000] or "(none)")
# grep teleautomation for fetch admin
_, o, _ = c.exec_command(
    f"grep -n 'admin' {REMOTE}/dashboard/src/teleautomation-app.jsx | grep -i 'fetch\\|/candidates\\|password' | head -20"
)
print("--- ta fetch ---")
print(o.read().decode("utf-8", errors="replace")[:3000])
c.close()
