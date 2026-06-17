import os
import paramiko

PWD = os.environ["VPS_PASSWORD"]
c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect("187.127.169.159", username="root", password=PWD, timeout=30)
_, o, _ = c.exec_command(
    "grep -rn 'resumes/' /opt/telegramforward.old/backups --include='server.py' 2>/dev/null | head -15; "
    "grep -rn 'Gopichand' /opt/telegramforward/data/candidates.json /opt/telegramforward.old/backups/pre_update_20260603_084737/data/candidates.json 2>/dev/null | head -5"
)
print(o.read().decode("utf-8", errors="replace"))
c.close()
