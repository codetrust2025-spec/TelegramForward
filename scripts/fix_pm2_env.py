#!/usr/bin/env python3
"""Fix: inject OLLAMA env vars into PM2 process environment."""
import paramiko

VPS_HOST = "187.127.169.159"
VPS_USER = "root"
VPS_PASSWORD = "8897870998s@SS"

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(VPS_HOST, username=VPS_USER, password=VPS_PASSWORD, timeout=30)

# Check how PM2 process gets its env - look at ecosystem config
cmd = """
# Check what env PM2 process actually has
cat /proc/$(pm2 pid telegram-backend)/environ 2>/dev/null | tr '\\0' '\\n' | grep OLLAMA || echo 'NO OLLAMA ENV IN PROCESS'

echo "---"

# Check how the app loads .env
grep -r 'dotenv\\|load_env\\|environ' /opt/telegramforward/scripts/uvicorn_reload.py 2>/dev/null | head -5
grep -r 'dotenv\\|load_env' /opt/telegramforward/run.py 2>/dev/null | head -5
grep -r 'dotenv' /opt/telegramforward/server.py 2>/dev/null | head -3

echo "---"

# Check ecosystem file
cat /opt/telegramforward/ecosystem.config.cjs 2>/dev/null | head -30
"""

stdin, stdout, stderr = ssh.exec_command(cmd, timeout=15)
print(stdout.read().decode())

ssh.close()
