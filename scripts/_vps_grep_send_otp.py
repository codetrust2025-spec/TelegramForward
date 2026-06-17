import os
import paramiko

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect("187.127.169.159", username="root", password=os.environ.get("VPS_PASSWORD", ""), timeout=30)
for cmd in [
    "grep -n 'send-otp' /root/.pm2/logs/telegram-backend-out.log | tail -15",
    "grep -n 'account11' /root/.pm2/logs/telegram-backend-error.log | tail -20",
    "PYTHONPATH=/opt/telegramforward /opt/telegramforward/venv/bin/python -c \"from core.config import ACCOUNTS; print('account11' in ACCOUNTS, list(ACCOUNTS.keys())[-3:])\"",
]:
    _, o, _ = c.exec_command(cmd, timeout=20)
    print(">>>", cmd[:60])
    print(o.read().decode())
c.close()
