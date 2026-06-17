"""Copy static bundle from telegramforward.old to nginx web root."""
from __future__ import annotations

import os
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import paramiko

PWD = os.environ.get("VPS_PASSWORD", "")
SRC = "/opt/telegramforward.old/static"
DST = "/opt/telegramforward/static"

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect("187.127.169.159", username="root", password=PWD, timeout=30)
cmd = f"rsync -a --delete {SRC}/ {DST}/ && ls -la {DST}/assets/*.js | tail -2"
_, o, e = c.exec_command(cmd, timeout=120)
print(o.read().decode("utf-8", errors="replace"))
err = e.read().decode("utf-8", errors="replace")
if err:
    print(err, file=sys.stderr)
c.close()
