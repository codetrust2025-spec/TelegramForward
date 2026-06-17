"""Add analytics + refresh-joined to nginx API proxy regex."""
import os
import paramiko

PWD = os.environ.get("VPS_PASSWORD", "")
NGINX = "/etc/nginx/sites-available/telegramforward"

OLD = "|workspace|favicon\\.ico|favicon\\.svg)"
NEW = "|workspace|analytics|refresh-joined|favicon\\.ico|favicon\\.svg)"

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect("187.127.169.159", username="root", password=PWD, timeout=30)

_, o, _ = c.exec_command(f"grep -n 'location ~' {NGINX}", timeout=30)
line = o.read().decode()
print("before:", line.strip()[:200])

if "analytics" in line:
    print("already has analytics")
else:
    sftp = c.open_sftp()
    with sftp.open(NGINX, "r") as f:
        content = f.read().decode("utf-8")
    if OLD not in content:
        raise SystemExit(f"pattern not found in {NGINX}")
    content = content.replace(OLD, NEW, 1)
    with sftp.open(NGINX, "w") as f:
        f.write(content.encode("utf-8"))
    sftp.close()
    print("patched")

for cmd in [
    "nginx -t 2>&1",
    "systemctl reload nginx",
    "grep -n 'location ~' /etc/nginx/sites-available/telegramforward",
    'curl -s -o /dev/null -w "pub:%{http_code} %{content_type}\\n" "https://teleautomation.online/analytics?days=30"',
    'curl -s "https://teleautomation.online/analytics?days=30" | head -c 80',
    'curl -s -o /dev/null -w "direct:%{http_code} %{content_type}\\n" "http://127.0.0.1:8000/analytics?days=30"',
    'curl -s "http://127.0.0.1:8000/analytics?days=30" | head -c 80',
]:
    print(">>>", cmd[:90])
    _, o, e = c.exec_command(cmd, timeout=60)
    print(o.read().decode("utf-8", errors="replace")[:400])
c.close()
