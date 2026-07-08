#!/usr/bin/env python3
"""Restart backend with Ollama env vars loaded."""
import paramiko

VPS_HOST = "187.127.169.159"
VPS_USER = "root"
VPS_PASSWORD = "8897870998s@SS"

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(VPS_HOST, username=VPS_USER, password=VPS_PASSWORD, timeout=30)

# Check current env in PM2 process
cmd = """
# First verify tunnel is still active
curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1:11434/api/tags

# Set env vars in PM2 process
pm2 set telegram-backend:OLLAMA_BASE_URL http://127.0.0.1:11434 2>/dev/null
pm2 restart telegram-backend --update-env

# Wait for startup
sleep 3

# Verify the process can reach Ollama
cd /opt/telegramforward && /opt/telegramforward/venv/bin/python3 -c "
import os
os.environ['OLLAMA_BASE_URL'] = 'http://127.0.0.1:11434'
os.environ['OLLAMA_VISION_MODEL'] = 'qwen2.5vl:7b'
from features.ollama_invite_extract import _is_ollama_available
print('Ollama available from Python:', _is_ollama_available())
"
"""

stdin, stdout, stderr = ssh.exec_command(cmd, timeout=30)
print(stdout.read().decode())
err = stderr.read().decode()
if err:
    print("STDERR:", err[:300])

ssh.close()
