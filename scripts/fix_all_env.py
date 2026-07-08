#!/usr/bin/env python3
"""Set ALL Ollama env vars in PM2 and restart."""
import paramiko

VPS_HOST = "187.127.169.159"
VPS_USER = "root"
VPS_PASSWORD = "8897870998s@SS"

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(VPS_HOST, username=VPS_USER, password=VPS_PASSWORD, timeout=30)

# Delete old PM2 process, recreate with env vars from .env
cmd = """
cd /opt/telegramforward

# Stop and delete current PM2 process
pm2 delete telegram-backend 2>/dev/null

# Start fresh with env vars from .env file using source
export $(grep -v '^#' .env | grep -v '^$' | xargs)

# Verify OLLAMA vars are in shell
echo "OLLAMA_BASE_URL=$OLLAMA_BASE_URL"
echo "OLLAMA_VISION_MODEL=$OLLAMA_VISION_MODEL"

# Start PM2 with current env (which now includes OLLAMA vars)
pm2 start scripts/uvicorn_reload.py --name telegram-backend --interpreter /opt/telegramforward/venv/bin/python3

# Wait for it to start
sleep 3

# Verify
pm2 list --no-color | grep telegram

# Test Ollama from the running process perspective
cat /proc/$(pm2 pid telegram-backend)/environ 2>/dev/null | tr '\\0' '\\n' | grep OLLAMA
"""

stdin, stdout, stderr = ssh.exec_command(cmd, timeout=30)
print(stdout.read().decode())
err = stderr.read().decode()
if err:
    print("ERR:", err[:200])

ssh.close()
