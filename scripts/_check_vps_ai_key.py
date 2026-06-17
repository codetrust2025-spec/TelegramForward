import os
import sys

import paramiko

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

PASSWORD = os.environ.get("VPS_PASSWORD", "")
client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect("187.127.169.159", username="root", password=PASSWORD, timeout=30)

checks = [
    "test -f /opt/telegramforward.old/.env && echo HAS_ENV || echo NO_ENV",
    "awk -F= '/^AI_API_KEY=/{print length($2)}' /opt/telegramforward.old/.env",
    "awk -F= '/^OPENAI_API_KEY=/{print length($2)}' /opt/telegramforward.old/.env",
]
for cmd in checks:
    stdin, stdout, stderr = client.exec_command(cmd, timeout=30)
    print(stdout.read().decode("utf-8", errors="replace").strip())

client.close()
