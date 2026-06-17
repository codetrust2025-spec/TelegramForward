import os
import sys

import paramiko

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

PASSWORD = os.environ.get("VPS_PASSWORD", "")
client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect("187.127.169.159", username="root", password=PASSWORD, timeout=30)

cmds = [
    "pm2 env 0 2>/dev/null | grep -E '^AI_API_KEY=|^OPENAI_API_KEY=' | awk -F= '{print $1 \" length=\" length($2)}'",
    "pm2 describe telegram-backend 2>/dev/null | grep -E 'exec cwd|script path' | head -4",
    "grep -E 'is_public_path|/ai/' /opt/telegramforward.old/core/dashboard_auth.py 2>/dev/null | head -20",
]
for cmd in cmds:
    print(">>>", cmd)
    stdin, stdout, stderr = client.exec_command(cmd, timeout=30)
    print(stdout.read().decode("utf-8", errors="replace"))

client.close()
