"""Diagnose blank TeleAutomation dashboard on VPS."""
from __future__ import annotations

import os
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
import paramiko

HOST, USER = "187.127.169.159", "root"
REMOTE = "/opt/telegramforward"
PWD = os.environ.get("VPS_PASSWORD", "")
PATH = f"{REMOTE}/dashboard/src/teleautomation-app.jsx"


def main() -> int:
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(HOST, username=USER, password=PWD, timeout=30)

    cmds = [
        f"tail -25 {PATH}",
        f"grep -n '_Component46' {PATH} | head -20",
        f"cat {REMOTE}/static/index.html",
        f"curl -s https://teleautomation.online/ | head -25",
        f"curl -s https://teleautomation.online/auth/status",
        f"curl -sI https://teleautomation.online/assets/index-D1YMOX_o.js | head -8",
        f"node -e \"const fs=require('fs');const p='{REMOTE}/static/assets/index-D1YMOX_o.js';const t=fs.readFileSync(p,'utf8');console.log('has AuthProvider wrap',t.includes('Component46')&&t.includes('TeleAutomationApp'));console.log('useAuth error string',t.includes('useAuth must be used'));\"",
        f"grep -n 'export default function TeleAutomationApp' {PATH}",
        f"grep -c 'wu()' {PATH}",
        f"grep -n 'function wu' {PATH}",
        f"grep -n 'function SR' {PATH}",
        f"grep -n 'PostingModePanel' {PATH} | head -5",
    ]
    for cmd in cmds:
        print("===", cmd[:100])
        _, o, e = c.exec_command(cmd, timeout=60)
        out = o.read().decode("utf-8", errors="replace")
        print(out[:6000] if out else "(empty)")
        err = e.read().decode()
        if err.strip():
            print("stderr:", err[:300])
    c.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
