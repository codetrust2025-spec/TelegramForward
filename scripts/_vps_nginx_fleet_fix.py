"""Add fleet (and forward-message) to nginx API proxy regex."""
import os
import sys

import paramiko

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

PWD = os.environ.get("VPS_PASSWORD", "")
NGINX = "/etc/nginx/sites-available/telegramforward"

# Match current production line (analytics already present)
OLD = "|workspace|analytics|refresh-joined|favicon\\.ico|favicon\\.svg)"
NEW = "|workspace|analytics|refresh-joined|fleet|forward-message|favicon\\.ico|favicon\\.svg)"

# Fallback if analytics patch never ran
OLD2 = "|workspace|favicon\\.ico|favicon\\.svg)"
NEW2 = "|workspace|fleet|forward-message|favicon\\.ico|favicon\\.svg)"

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect("187.127.169.159", username="root", password=PWD, timeout=30)

_, o, _ = c.exec_command(f"grep -n 'location ~' {NGINX}", timeout=30)
line = o.read().decode()
print("before:", line.strip()[:220])

if "fleet" in line:
    print("already has fleet")
else:
    sftp = c.open_sftp()
    with sftp.open(NGINX, "r") as f:
        content = f.read().decode("utf-8")
    if OLD in content:
        content = content.replace(OLD, NEW, 1)
    elif OLD2 in content:
        content = content.replace(OLD2, NEW2, 1)
    else:
        raise SystemExit(f"pattern not found in {NGINX}")
    with sftp.open(NGINX, "w") as f:
        f.write(content.encode("utf-8"))
    sftp.close()
    print("patched nginx")

for cmd in [
    "nginx -t 2>&1",
    "systemctl reload nginx",
    'curl -s -o /dev/null -w "fleet:%{http_code} %{content_type}\\n" https://teleautomation.online/fleet/defaults',
    'curl -s https://teleautomation.online/fleet/defaults | head -c 120',
]:
    print(">>>", cmd)
    _, o, _ = c.exec_command(cmd, timeout=60)
    print(o.read().decode("utf-8", errors="replace")[:400])
c.close()
