import os
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
import paramiko

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect("187.127.169.159", username="root", password=os.environ["VPS_PASSWORD"], timeout=30)
_, o, _ = c.exec_command("cat /etc/nginx/sites-available/telegramforward", timeout=60)
print(o.read().decode("utf-8", errors="replace"))
c.close()
