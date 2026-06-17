import os
import paramiko

PWD = os.environ.get("VPS_PASSWORD", "")
c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect("187.127.169.159", username="root", password=PWD, timeout=30)
for cmd in [
    "grep -c '.admin-dashboard' /opt/telegramforward/dashboard/src/index.css 2>/dev/null || echo 0",
    "grep -c '.admin-dashboard' /opt/telegramforward.old/dashboard/src/index.css 2>/dev/null || echo 0",
    "find /opt/telegramforward -name '*.css' -exec grep -l admin-dashboard {} \\; 2>/dev/null | head -5",
]:
    _, o, _ = c.exec_command(cmd, timeout=60)
    print(cmd)
    print(o.read().decode("utf-8", errors="replace"))
c.close()
