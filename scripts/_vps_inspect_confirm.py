"""Inspect ConfirmProvider wiring on VPS."""
from __future__ import annotations

import os
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
import paramiko

REMOTE = "/opt/telegramforward"
c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect("187.127.169.159", "root", password=os.environ.get("VPS_PASSWORD", ""), timeout=30)

cmds = [
    f"cat {REMOTE}/dashboard/src/main.jsx",
    f"grep -n 'ConfirmProvider\\|useConfirm\\|ConfirmContext' {REMOTE}/dashboard/src/teleautomation-app.jsx | head -30",
    f"grep -n 'useConfirm' {REMOTE}/dashboard/src/components/PostingModePanel.jsx",
    f"curl -s https://teleautomation.online/ | grep -o 'index-[^.]*.js'",
    f"node -e \"const fs=require('fs');const p='{REMOTE}/static/assets/index-C8db0XzP.js';const t=fs.readFileSync(p,'utf8');const a=t.indexOf('useConfirm must');const b=t.match(/ConfirmProvider/g);console.log('confirm err',a>=0);console.log('ConfirmProvider count',b?b.length:0);const i=t.indexOf('createRoot');console.log('createRoot snippet',t.slice(i,i+400));\"",
]
for cmd in cmds:
    print("===", cmd[:95])
    _, o, e = c.exec_command(cmd, timeout=90)
    print(o.read().decode("utf-8", errors="replace")[:5000])
    err = e.read().decode().strip()
    if err:
        print("stderr:", err[:300])
c.close()
