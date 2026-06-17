import os
import paramiko

PWD = os.environ.get("VPS_PASSWORD", "")
c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect("187.127.169.159", username="root", password=PWD, timeout=30)
_, o, _ = c.exec_command("cat /etc/nginx/sites-available/telegramforward", timeout=60)
print(o.read().decode("utf-8", errors="replace"))
_, o, _ = c.exec_command("grep -n '@app\\|register\\|push' /opt/telegramforward.old/features/web_push.py | head -40", timeout=60)
print("--- web_push routes ---")
print(o.read().decode())
c.close()
