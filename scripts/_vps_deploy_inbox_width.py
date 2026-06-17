"""Build dashboard and deploy static assets after inbox list width tweak."""
from __future__ import annotations

import os
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import paramiko

HOST, USER = "187.127.169.159", "root"
REMOTE_UI = "/opt/telegramforward"
REMOTE_OLD = "/opt/telegramforward.old"
PWD = os.environ.get("VPS_PASSWORD", "")
LOCAL_CSS = os.path.join(
    os.path.dirname(os.path.dirname(__file__)),
    "dashboard",
    "src",
    "index.css",
)

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(HOST, username=USER, password=PWD, timeout=30)

sftp = c.open_sftp()
sftp.put(LOCAL_CSS, f"{REMOTE_UI}/dashboard/src/index.css")
print("uploaded index.css")
sftp.close()

cmds = [
    f"cd {REMOTE_UI}/dashboard && npm run build 2>&1 | tail -12",
    f"cd {REMOTE_UI} && bash scripts/production_update.sh 2>&1 | tail -15",
    f"grep -o 'clamp(300px, 32vw, 420px)' {REMOTE_UI}/static/assets/*.css 2>/dev/null | head -1 || "
    f"grep -o 'clamp(300px, 32vw, 420px)' {REMOTE_UI}/static/assets/*.js 2>/dev/null | head -1 || "
    "echo VERIFY_MISSING",
]
for cmd in cmds:
    print(">>>", cmd[:100])
    _, o, e = c.exec_command(cmd, timeout=300000)
    out = o.read().decode("utf-8", errors="replace")
    print(out[-2500:] if len(out) > 2500 else out)
    err = e.read().decode("utf-8", errors="replace")
    if err.strip():
        print("ERR:", err[-800:])
c.close()
