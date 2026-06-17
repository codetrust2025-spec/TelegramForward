import os
import paramiko

PWD = os.environ.get("VPS_PASSWORD", "")
NGINX = "/etc/nginx/sites-available/telegramforward"

# Current regex segment from earlier deploy
c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect("187.127.169.159", username="root", password=PWD, timeout=30)
_, o, _ = c.exec_command(f"grep -n 'location ~' {NGINX}", timeout=30)
line = o.read().decode()
print("current:", line)

ADD = ["analytics", "refresh-joined", "progress", "system", "handlers", "demo-tools"]
if "analytics" not in line:
    new_line = line.replace(
        "handler-salaries|alerts|workspace|favicon",
        "handler-salaries|alerts|workspace|analytics|refresh-joined|progress|system|handlers|favicon",
        1,
    )
    if new_line == line:
        # fallback: insert before favicon
        new_line = line.replace("|favicon", "|analytics|refresh-joined|progress|system|handlers|favicon", 1)
    sftp = c.open_sftp()
    with sftp.open(NGINX, "r") as f:
        content = f.read().decode("utf-8")
    content = content.replace(line.strip(), new_line.strip(), 1)
    with sftp.open(NGINX, "w") as f:
        f.write(content.encode("utf-8"))
    sftp.close()
    print("patched nginx")
else:
    print("analytics already in nginx")

for cmd in [
    "nginx -t 2>&1",
    "systemctl reload nginx",
    "curl -s -o /dev/null -w '%{http_code} %{content_type}' https://teleautomation.online/analytics?days=30",
    "curl -s https://teleautomation.online/analytics?days=30 | head -c 60",
    "curl -s -o /dev/null -w '%{http_code} %{content_type}' https://teleautomation.online/refresh-joined",
    "curl -s https://teleautomation.online/refresh-joined | head -c 60",
]:
    print(">>>", cmd[:80])
    _, o, _ = c.exec_command(cmd, timeout=60)
    print(o.read().decode("utf-8", errors="replace")[:300])
c.close()
