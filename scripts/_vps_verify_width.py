import os
import paramiko

PWD = os.environ.get("VPS_PASSWORD", "")
c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect("187.127.169.159", username="root", password=PWD, timeout=30)
_, o, _ = c.exec_command(
    r'grep -l "clamp(300px, 32vw, 420px)" /opt/telegramforward/static/assets/* 2>/dev/null; '
    r'grep -o "index-[^\"]*\.css" /opt/telegramforward/static/index.html | head -1',
    timeout=30,
)
print(o.read().decode("utf-8", errors="replace"))
c.close()
