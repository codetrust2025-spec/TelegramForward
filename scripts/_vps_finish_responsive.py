import os
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
import paramiko

PWD = os.environ.get("VPS_PASSWORD", "")
REMOTE = "/opt/telegramforward"
cmds = [
    f"cd {REMOTE} && node scripts/_patch_confirm.js",
    f"grep index.html {REMOTE}/static/index.html",
    f"ls -la {REMOTE}/static/assets/*.css",
    "curl -sf http://127.0.0.1:8000/health",
]
c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect("187.127.169.159", username="root", password=PWD, timeout=30)
for cmd in cmds:
    print(">>>", cmd)
    _, o, e = c.exec_command(cmd, timeout=120)
    code = o.channel.recv_exit_status()
    print(o.read().decode())
    if e.read().decode().strip():
        print("err:", e.read().decode())
    print("exit", code)
c.close()
