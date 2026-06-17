import os
import paramiko

PWD = os.environ["VPS_PASSWORD"]
c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect("187.127.169.159", username="root", password=PWD, timeout=30)
_, o, _ = c.exec_command(
    "grep -rl '7a6a68d247\\|Gopichand' /opt/telegramforward.old/backups /opt/telegramforward/data 2>/dev/null | head -20"
)
print(o.read().decode("utf-8", errors="replace"))
c.close()
