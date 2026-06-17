import os
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
import paramiko

PWD = os.environ.get("VPS_PASSWORD", "")
c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect("187.127.169.159", username="root", password=PWD, timeout=30)
cmds = [
    "grep -n data-room /etc/nginx/sites-enabled/* 2>/dev/null | head -20",
    'curl -s -o /dev/null -w "public:%{http_code} ct:%{content_type} t:%{time_total}\\n" https://teleautomation.online/data-room/credentials',
    "curl -s https://teleautomation.online/data-room/credentials | head -c 120",
    "curl -s https://teleautomation.online/ | grep -o 'app-[A-Za-z0-9_\\-]*\\.js' | head -1",
]
for cmd in cmds:
    print(">>>", cmd)
    _, o, e = c.exec_command(cmd, timeout=30)
    print(o.read().decode()[:500])
c.close()
