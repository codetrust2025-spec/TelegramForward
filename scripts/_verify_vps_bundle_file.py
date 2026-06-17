import os
import sys
import paramiko

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
PASSWORD = os.environ.get("VPS_PASSWORD", "")
client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect("187.127.169.159", username="root", password=PASSWORD, timeout=30)
for path in [
    "/opt/telegramforward.old/static/assets/app-9YCr_3F-.js",
    "/opt/telegramforward/static/assets/app-9YCr_3F-.js",
]:
    stdin, stdout, stderr = client.exec_command(f"ls -la {path} 2>&1", timeout=20)
    print(stdout.read().decode())
client.close()
