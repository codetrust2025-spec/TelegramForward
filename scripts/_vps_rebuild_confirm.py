"""Rebuild dashboard and patch confirm (avoid CRLF production_update.sh)."""
from __future__ import annotations

import os
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import paramiko

HOST, USER, REMOTE = "187.127.169.159", "root", "/opt/telegramforward"
PWD = os.environ.get("VPS_PASSWORD", "")

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(HOST, username=USER, password=PWD, timeout=30)

cmds = [
    f"cd {REMOTE}/dashboard && npm run build 2>&1 | tail -12",
    f"cd {REMOTE} && node scripts/_patch_confirm.js 2>&1",
    "pm2 restart telegram-backend 2>&1 | tail -5",
    r"""node -e "
const fs=require('fs');
const html=fs.readFileSync('/opt/telegramforward/static/index.html','utf8');
const m=html.match(/assets\/(app-[^\"]+\.js)/);
const t=fs.readFileSync('/opt/telegramforward/static/assets/'+m[1],'utf8');
console.log('bundle', m[1]);
console.log('eo', t.includes('__TA_CONFIRM_VALUE__'));
console.log('unmount clear', t.includes('globalThis[rd]===l&&(globalThis[rd]=null)'));
console.log('inline global set', t.includes('globalThis.__TA_CONFIRM_VALUE__={confirm:'));
" """,
]
for cmd in cmds:
    print(">>>", cmd[:90])
    _, o, e = c.exec_command(cmd, timeout=600000)
    print(o.read().decode("utf-8", errors="replace")[-2500:])
    err = e.read().decode("utf-8", errors="replace")
    if err.strip():
        print("ERR:", err[-400:])
c.close()
