"""Find LB reference causing blank page."""
from __future__ import annotations

import os
import re
import sys

import paramiko

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

PWD = os.environ.get("VPS_PASSWORD", "")
REMOTE = "/opt/telegramforward/static/assets/app-K3HiHVlR.js"
LOCAL = os.path.join(os.path.dirname(os.path.dirname(__file__)), "static", "assets", "_live_app.js")

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect("187.127.169.159", username="root", password=PWD, timeout=30)
sftp = c.open_sftp()
sftp.get(REMOTE, LOCAL)
sftp.close()
c.close()

t = open(LOCAL, encoding="utf-8").read()
print("size", len(t))
print("ops-dashboard--v3", t.find("ops-dashboard--v3"))
print("LB( count", t.count("LB("))

for m in re.finditer(r"[^A-Za-z0-9_$]LB[^A-Za-z0-9_$]", t):
    i = m.start() + 1
    ctx = t[max(0, i - 100) : i + 100]
    if "function LB" in ctx or "LB(t,e" in ctx:
        continue
    if "961:" in ctx and "LB" in ctx:
        continue
    print("LB ref at", i)
    print(repr(ctx))
    break

# missing deps from core at runtime - search O0 Y5 D_
for name in ["O0(", "Y5(", "D_(", "fP("]:
    idx = t.find(name)
    print(name, "first at", idx)
