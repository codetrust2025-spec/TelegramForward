import os
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
import paramiko

PWD = os.environ.get("VPS_PASSWORD", "")
c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect("187.127.169.159", username="root", password=PWD, timeout=30)
cmds = [
    "pm2 list",
    "curl -sf -m 5 http://127.0.0.1:8000/health || echo HEALTH_FAIL",
    "grep -r 'location /ws' /etc/nginx/sites-enabled/ /etc/nginx/conf.d/ 2>/dev/null | head -8",
    "cat /etc/nginx/sites-enabled/telegramforward 2>/dev/null | head -80",
    "tail -25 /root/.pm2/logs/telegram-backend-error.log 2>/dev/null",
]
for cmd in cmds:
    print(">>>", cmd)
    _i, o, _e = c.exec_command(cmd, timeout=30)
    print(o.read().decode("utf-8", errors="replace")[:4000])
c.close()
