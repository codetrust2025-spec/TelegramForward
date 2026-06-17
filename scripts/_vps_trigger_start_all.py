import os
import sys
import time
import paramiko

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
REMOTE = "/opt/telegramforward"
PY = f"{REMOTE}/venv/bin/python"

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect("187.127.169.159", username="root", password=os.environ["VPS_PASSWORD"], timeout=30)

def run(cmd):
    _, o, e = ssh.exec_command(cmd, timeout=300)
    return (o.read() + e.read()).decode("utf-8", "replace")

print(run(f"cd {REMOTE} && PYTHONPATH={REMOTE} {PY} scripts/_vps_verify_karthik_once.py"))
time.sleep(45)
print(run(
    "pm2 logs telegram-backend --nostream --lines 50 2>/dev/null "
    "| grep -iE 'ai_smart_reply send|enqueued|karthik_inbox' | tail -15"
))
ssh.close()
