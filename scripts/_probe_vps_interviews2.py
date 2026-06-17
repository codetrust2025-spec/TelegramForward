"""Find interview route registration on VPS."""
import os, paramiko
PWD = os.environ.get("VPS_PASSWORD", "")
c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect("187.127.169.159", username="root", password=PWD, timeout=30)
for cmd in [
    "grep -rn 'interview' /opt/telegramforward/server.py /opt/telegramforward/features/*.py 2>/dev/null | head -60",
    "grep -rn 'interviews/' /opt/telegramforward --include='*.py' | head -40",
]:
    print("===", cmd[:70])
    _, o, _ = c.exec_command(cmd)
    print(o.read().decode("utf-8", errors="replace")[:5000])
c.close()
