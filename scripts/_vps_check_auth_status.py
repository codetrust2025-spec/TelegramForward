import os
import paramiko

PWD = os.environ.get("VPS_PASSWORD", "")
c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect("187.127.169.159", username="root", password=PWD, timeout=30)
for cmd in [
    "grep -n install_dashboard_auth /opt/telegramforward/server.py | head -5",
    "grep DASHBOARD_PASSWORD /opt/telegramforward/.env 2>/dev/null | sed 's/=.*/=*** /'",
    'curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:8000/auth/status',
    "curl -s http://127.0.0.1:8000/auth/status",
]:
    print(">>>", cmd)
    _, o, e = c.exec_command(cmd)
    print(o.read().decode() or e.read().decode())
c.close()
