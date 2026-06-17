"""Probe Vani phone on VPS and PATCH edit route."""
from __future__ import annotations

import os
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import paramiko

PWD = os.environ.get("VPS_PASSWORD", "")
REMOTE = "/opt/telegramforward.old"
c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect("187.127.169.159", username="root", password=PWD, timeout=30)
cmds = [
    f"cat {REMOTE}/data/accounts/account10/account_info.json 2>/dev/null | head -c 500",
    f"grep VANI_ {REMOTE}/core/ai_smart_reply.py",
    (
        "curl -s -o /tmp/patch_out -w '%{http_code}' -X PATCH "
        "http://127.0.0.1:8000/inbox/account10/messages/1/1 "
        "-H 'Content-Type: application/json' -d '{\"text\":\"test\"}' ; "
        "echo ; head -c 200 /tmp/patch_out"
    ),
    "grep -l 'patchInboxMessage' /opt/telegramforward/static/assets/*.js 2>/dev/null | head -2 || echo NO_PATCH_IN_STATIC",
    "grep -c 'method:\"PATCH\"' /opt/telegramforward/static/assets/app-*.js 2>/dev/null | head -3",
]
for cmd in cmds:
    print("===", cmd[:90])
    _, o, _ = c.exec_command(cmd, timeout=30)
    print(o.read().decode("utf-8", errors="replace"))
c.close()
