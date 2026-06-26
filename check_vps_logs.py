import paramiko
import sys
import os

sys.stdout.reconfigure(encoding='utf-8', errors='replace')

PASSWORD = os.environ.get('VPS_PASSWORD', 'REMOVED_VPS_PASSWORD')

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect('187.127.169.159', username='root', password=PASSWORD, timeout=30)

# Check the output log for OCR-related messages
cmd = 'tail -100 /root/.pm2/logs/telegram-backend-out.log'
print('>>>', cmd)
_, stdout, stderr = client.exec_command(cmd, timeout=60)
out = stdout.read().decode('utf-8', errors='replace')
err = stderr.read().decode('utf-8', errors='replace')
print(out)
if err.strip():
    print('STDERR:', err.strip(), file=sys.stderr)

client.close()
