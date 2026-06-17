"""Register web push routes + verify nginx proxies API paths."""
import os
import paramiko

PWD = os.environ.get("VPS_PASSWORD", "")
REMOTE = "/opt/telegramforward.old"
c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect("187.127.169.159", username="root", password=PWD, timeout=30)

cmds = [
    f"grep -n 'push\\|web_push' {REMOTE}/server.py | head -25",
    f"grep -n 'def install\\|@app' {REMOTE}/features/web_push.py | head -30",
    "grep -rn 'location /' /etc/nginx/sites-enabled/ 2>/dev/null | head -40",
    "curl -s -o /dev/null -w '%{http_code} %{content_type}\\n' https://teleautomation.online/alerts",
    "curl -s https://teleautomation.online/alerts | head -c 80",
]
for cmd in cmds:
    print("===", cmd[:95])
    _, o, _ = c.exec_command(cmd, timeout=60)
    print(o.read().decode("utf-8", errors="replace")[:2000])

c.close()
