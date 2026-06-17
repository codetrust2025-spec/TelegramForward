"""Add /alerts to nginx API proxy; register web push routes on server."""
from __future__ import annotations

import os
import paramiko

PWD = os.environ.get("VPS_PASSWORD", "")
REMOTE = "/opt/telegramforward.old"
NGINX = "/etc/nginx/sites-available/telegramforward"
REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

INSTALL = (
    "from core.web_push_api import install_web_push_routes\n"
    "install_web_push_routes(app)\n"
)

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect("187.127.169.159", username="root", password=PWD, timeout=30)
sftp = c.open_sftp()

# Upload web_push_api module
sftp.put(
    os.path.join(REPO, "core", "web_push_api.py"),
    f"{REMOTE}/core/web_push_api.py",
)
print("uploaded core/web_push_api.py")

# nginx: add alerts to regex
with sftp.open(NGINX, "r") as f:
    nginx = f.read().decode("utf-8")
if "alerts|" not in nginx and "|alerts|" not in nginx:
    nginx = nginx.replace(
        "handler-expenses|handler-salaries|favicon",
        "handler-expenses|handler-salaries|alerts|workspace|favicon",
        1,
    )
    with sftp.open(NGINX, "w") as f:
        f.write(nginx.encode("utf-8"))
    print("patched nginx: alerts|workspace")
else:
    print("nginx already has alerts")

with sftp.open(f"{REMOTE}/server.py", "r") as f:
    server = f.read().decode("utf-8")

if "install_web_push_routes" not in server:
    needle = "install_admin_dashboard(app)"
    if needle in server:
        server = server.replace(
            needle,
            needle + "\n\n" + INSTALL.rstrip(),
            1,
        )
        print("wired install_web_push_routes")
    else:
        print("WARN: no insert point for web push")
    with sftp.open(f"{REMOTE}/server.py", "w") as f:
        f.write(server.encode("utf-8"))
else:
    print("web push routes already wired")

sftp.close()

for cmd in [
    "nginx -t 2>&1",
    "systemctl reload nginx",
    "pm2 restart telegram-backend",
    "sleep 10",
    "curl -s -o /dev/null -w '%{http_code} %{content_type}' https://teleautomation.online/alerts",
    "curl -s https://teleautomation.online/alerts | head -c 80",
    "curl -s http://127.0.0.1:8000/push/vapid-public-key | head -c 120",
    "curl -s -o /dev/null -w '%{http_code}' https://teleautomation.online/push/vapid-public-key",
]:
    print(">>>", cmd[:85])
    _, o, _ = c.exec_command(cmd, timeout=120)
    print(o.read().decode("utf-8", errors="replace")[:400])

c.close()
print("done")
