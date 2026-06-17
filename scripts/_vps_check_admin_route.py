import os
import paramiko

PWD = os.environ.get("VPS_PASSWORD", "")
c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect("187.127.169.159", username="root", password=PWD, timeout=30)
for cmd in [
    "grep -rn 'admin/dashboard\\|install_admin' /opt/telegramforward.old/server.py /opt/telegramforward.old/core/ 2>/dev/null | head -15",
    "curl -s -o /dev/null -w '%{http_code}' 'http://127.0.0.1:8000/admin/dashboard?window_hours=24'",
]:
    _, o, _ = c.exec_command(cmd, timeout=30)
    print(cmd)
    print(o.read().decode("utf-8", errors="replace"))
c.close()
