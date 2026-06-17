import os
import sys

import paramiko

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect("187.127.169.159", username="root", password=os.environ.get("VPS_PASSWORD", ""), timeout=30)
cmds = [
    "grep -r fleet /etc/nginx/ 2>/dev/null | head -20",
    "grep -r 'location' /etc/nginx/sites-enabled/ 2>/dev/null | head -40",
    "cat /etc/nginx/sites-enabled/* 2>/dev/null | head -120",
]
for cmd in cmds:
    _, o, _ = c.exec_command(cmd, timeout=25)
    print(">>>", cmd[:70])
    out = o.read().decode("utf-8", "replace")
    print(out[:4000] if out else "(empty)")
c.close()
