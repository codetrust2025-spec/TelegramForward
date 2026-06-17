import os
import paramiko

PWD = os.environ.get("VPS_PASSWORD", "")
c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect("187.127.169.159", username="root", password=PWD, timeout=30)
cmds = [
    "ls -la /etc/nginx/sites-enabled/",
    "cat /etc/nginx/sites-enabled/teleautomation* 2>/dev/null || cat /etc/nginx/sites-enabled/default 2>/dev/null",
    "grep -rn teleautomation /etc/nginx/ 2>/dev/null | head -20",
]
for cmd in cmds:
    print("===", cmd)
    _, o, _ = c.exec_command(cmd, timeout=60)
    print(o.read().decode("utf-8", errors="replace")[:8000])
c.close()
