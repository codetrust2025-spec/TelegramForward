import os
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import paramiko

PWD = os.environ.get("VPS_PASSWORD", "")
c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect("187.127.169.159", username="root", password=PWD, timeout=30)
cmds = [
    "pm2 status",
    "pm2 logs telegram-backend --lines 40 --nostream 2>&1 | tail -45",
    'curl -s -o /dev/null -w "health:%{http_code}\\n" http://127.0.0.1:8000/health || echo curl_failed',
    "cd /opt/telegramforward && python3 -c \"import server\" 2>&1 | tail -20",
]
for cmd in cmds:
    print(">>>", cmd)
    _, o, e = c.exec_command(cmd, timeout=60)
    out = o.read().decode("utf-8", errors="replace")
    err = e.read().decode("utf-8", errors="replace")
    print(out or err)
c.close()
