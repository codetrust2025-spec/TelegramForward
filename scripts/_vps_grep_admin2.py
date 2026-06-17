import os
import paramiko

PWD = os.environ.get("VPS_PASSWORD", "")
c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect("187.127.169.159", username="root", password=PWD, timeout=30)
cmds = [
    "grep -n 'DASHBOARD_PASSWORD\\|dashboard.password\\|verify_admin\\|admin.*unlock\\|/auth' /opt/telegramforward/server.py | head -40",
    "grep -n 'admin-password\\|admin/password\\|verify-password' /opt/telegramforward/server.py /opt/telegramforward/dashboard/src/teleautomation-app.jsx 2>/dev/null | head -20",
    "sed -n '37430,37520p' /opt/telegramforward/dashboard/src/teleautomation-app.jsx",
]
for cmd in cmds:
    print(">>>", cmd[:80])
    _, o, _ = c.exec_command(cmd, timeout=60)
    print(o.read().decode("utf-8", errors="replace")[:5000])
    print()
c.close()
