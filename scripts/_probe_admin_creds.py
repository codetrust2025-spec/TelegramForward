import os
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
import paramiko

PWD = os.environ.get("VPS_PASSWORD", "")
REMOTE = "/opt/telegramforward"
c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect("187.127.169.159", username="root", password=PWD, timeout=30)
cmds = [
    f"grep -E 'DASHBOARD|ADMIN' {REMOTE}/.env 2>/dev/null | sed 's/=.*/=***/'",
    f"cd {REMOTE} && venv/bin/python -c \"from core import dashboard_auth_vps as a; u,p=a.get_credentials(); print('user',u,'pwd_len',len(p or ''))\"",
]
for cmd in cmds:
    _, o, e = c.exec_command(cmd, timeout=30)
    print(o.read().decode())
    err = e.read().decode()
    if err:
        print("ERR:", err[:200])
c.close()
