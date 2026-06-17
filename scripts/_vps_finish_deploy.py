import os
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.stderr.reconfigure(encoding="utf-8", errors="replace")

import paramiko

HOST, USER, REMOTE = "187.127.169.159", "root", "/opt/telegramforward"
PWD = os.environ.get("VPS_PASSWORD", "")
cmds = [
    f"cd {REMOTE}/dashboard && npm run build",
    f"cd {REMOTE} && bash scripts/production_update.sh",
    f'grep -l "Posting mode" {REMOTE}/static/assets/*.js 2>/dev/null || '
    f'grep -l "Posting mode" {REMOTE}/dashboard/dist/assets/*.js 2>/dev/null || '
    "echo VERIFY_FAIL",
    "pm2 list 2>/dev/null | head -10",
]
c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(HOST, username=USER, password=PWD, timeout=30)
for cmd in cmds:
    print(">>>", cmd)
    _, o, e = c.exec_command(cmd, timeout=600)
    code = o.channel.recv_exit_status()
    print(o.read().decode("utf-8", errors="replace"))
    err = e.read().decode("utf-8", errors="replace")
    if err:
        print("stderr:", err)
    print("exit", code)
c.close()
