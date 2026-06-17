import os
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
import paramiko

REMOTE = "/opt/telegramforward.old"
OUT = os.path.join(os.path.dirname(os.path.dirname(__file__)), "core", "admin_dashboard_vps.py")
c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect("187.127.169.159", "root", password=os.environ.get("VPS_PASSWORD", ""), timeout=30)
sftp = c.open_sftp()
sftp.get(f"{REMOTE}/core/admin_dashboard.py", OUT)
sftp.close()

cmds = [
    f"grep -n 'admin_dashboard\\|install_admin\\|/admin/' {REMOTE}/server.py | head -40",
    "curl -s -o /dev/null -w '%{http_code}' 'http://127.0.0.1:8000/admin/dashboard?window_hours=24'",
    "curl -s 'http://127.0.0.1:8000/admin/dashboard?window_hours=24' | head -c 300",
]
for cmd in cmds:
    print("===", cmd)
    _, o, _ = c.exec_command(cmd, timeout=60)
    print(o.read().decode("utf-8", errors="replace"))
c.close()
print("saved", OUT)
