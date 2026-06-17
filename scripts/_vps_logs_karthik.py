import os
import sys
import time
import paramiko

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
time.sleep(20)
ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect("187.127.169.159", username="root", password=os.environ["VPS_PASSWORD"], timeout=30)
_, o, e = ssh.exec_command(
    "pm2 logs telegram-backend --nostream --lines 250 2>/dev/null "
    "| grep -iE 'ai_smart|karthik_inbox|enqueued|generate_and|llm_error|inbox_sweep|AI_AUTO' | tail -30",
    timeout=60,
)
print((o.read() + e.read()).decode())
ssh.close()
