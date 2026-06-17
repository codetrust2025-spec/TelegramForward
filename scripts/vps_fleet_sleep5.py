#!/usr/bin/env python3
import socket, paramiko, sys, re
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
PASSWORD = "REMOVED_VPS_PASSWORD"
sock = socket.create_connection(("187.127.169.159", 22), timeout=30)
c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(hostname="187.127.169.159", username="root", password=PASSWORD, sock=sock)

cmds = [
    "grep -rn 'minCountdown\\|sleepingCount\\|\"fleet\"' /opt/telegramforward.old/services /opt/telegramforward.old/api /opt/telegramforward.old/main.py 2>/dev/null | head -40",
    "grep -rn 'build_fleet\\|fleet_summary\\|perAccount' /opt/telegramforward.old --include='*.py' 2>/dev/null | head -30",
]
for cmd in cmds:
    print("===", cmd[:70])
    _, stdout, _ = c.exec_command(cmd, timeout=90)
    print(stdout.read().decode("utf-8", errors="replace")[:8000])

# extract Ds function and fleet panel logic from JS
_, stdout, _ = c.exec_command(
    "python3 -c \"import re; s=open('/opt/telegramforward.old/static/assets/app-BkUk1ts9.js',encoding='utf-8',errors='ignore').read(); "
    "for pat in [r'function Ds\\([^)]*\\)\\{[^}]{0,200}\\}', r'minCountdown[^,]{0,200}', r'sleeping[^,]{0,120}countdown']: "
    " m=re.search(pat,s); print('---',pat,'---'); print(m.group(0)[:300] if m else 'none')\"",
    timeout=60,
)
print("=== JS snippets ===")
print(stdout.read().decode("utf-8", errors="replace"))

c.close()
