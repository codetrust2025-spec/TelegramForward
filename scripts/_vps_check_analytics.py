import os
import paramiko

PWD = os.environ.get("VPS_PASSWORD", "")
c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect("187.127.169.159", username="root", password=PWD, timeout=30)
cmds = [
    "grep -n 'location ~' /etc/nginx/sites-available/telegramforward",
    'curl -s -o /dev/null -w "direct:%{http_code} %{content_type}\\n" "http://127.0.0.1:8000/analytics?days=30"',
    'curl -s "http://127.0.0.1:8000/analytics?days=30" | head -c 100',
    "grep -rn 'analytics' /opt/telegramforward.old/server.py /opt/telegramforward.old/core/ 2>/dev/null | head -20",
    "pm2 list | head -8",
]
for cmd in cmds:
    print(">>>", cmd)
    _, o, e = c.exec_command(cmd, timeout=60)
    print(o.read().decode("utf-8", errors="replace")[:800])
    err = e.read().decode("utf-8", errors="replace")
    if err.strip():
        print("ERR:", err[:300])
c.close()
