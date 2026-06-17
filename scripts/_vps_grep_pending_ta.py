import os
import re
import paramiko

PWD = os.environ.get("VPS_PASSWORD", "")
c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect("187.127.169.159", username="root", password=PWD, timeout=30)

paths = [
    "/opt/telegramforward/dashboard/src/teleautomation-app.jsx",
    "/opt/telegramforward.old/dashboard/src/teleautomation-app.jsx",
]
for p in paths:
    print("===", p, "===")
    _, o, _ = c.exec_command(f"test -f {p} && wc -c {p} || echo MISSING")
    print(o.read().decode().strip())
    _, o, _ = c.exec_command(
        f"grep -o '.{{0,80}}Pending.{{0,80}}' {p} 2>/dev/null | head -15"
    )
    out = o.read().decode("utf-8", "replace")
    print(out.encode("ascii", "replace").decode())
c.close()
