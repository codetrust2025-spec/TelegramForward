import os
import sys
import time

import paramiko

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect("187.127.169.159", username="root", password=os.environ["VPS_PASSWORD"], timeout=30)

def run(cmd):
    _, o, e = ssh.exec_command(cmd, timeout=120)
    return (o.read() + e.read()).decode("utf-8", "replace")

time.sleep(12)
print("=== PM2 env AI key ===")
print(run("pm2 env 0 2>/dev/null | grep -E '^AI_|^OPENAI_' | sed 's/=.*/=***/'"))

print("\n=== ai logs ===")
print(run(
    "pm2 logs telegram-backend --nostream --lines 120 2>/dev/null "
    "| grep -iE 'ai_smart|karthik|llm_error|ai_disabled|enqueued|generate_and|inbox_sweep' "
    "| tail -35"
))

print("\n=== sweep ===")
print(run(
    "cd /opt/telegramforward && PYTHONPATH=/opt/telegramforward "
    "/opt/telegramforward/venv/bin/python -c "
    "'from core.karthik_inbox_sweep import status; print(status())'"
))

ssh.close()
