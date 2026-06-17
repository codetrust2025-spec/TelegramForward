import os
import sys
import time
import paramiko

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REMOTE = "/opt/telegramforward"
PY = f"{REMOTE}/venv/bin/python"

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect("187.127.169.159", username="root", password=os.environ["VPS_PASSWORD"], timeout=30)
sftp = ssh.open_sftp()
sftp.put(os.path.join(root, "core", "config.py"), f"{REMOTE}/core/config.py")
sftp.close()

def run(cmd):
    _, o, e = ssh.exec_command(cmd, timeout=180)
    return (o.read() + e.read()).decode()

print(run(f"cd {REMOTE} && PYTHONPATH={REMOTE} pm2 restart telegram-backend --update-env"))
time.sleep(15)
print(run(f"cd {REMOTE} && PYTHONPATH={REMOTE} {PY} scripts/_vps_verify_karthik_once.py"))
print(run(
    "pm2 logs telegram-backend --nostream --lines 60 2>/dev/null "
    "| grep -iE 'ai_smart_reply send|enqueued|karthik_inbox' | tail -15"
))
ssh.close()
