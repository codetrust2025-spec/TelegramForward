#!/usr/bin/env python3
"""Configure backend to use local VPS Ollama moondream."""
import paramiko

VPS_HOST = "187.127.169.159"
VPS_USER = "root"
VPS_PASSWORD = "8897870998s@SS"

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(VPS_HOST, username=VPS_USER, password=VPS_PASSWORD, timeout=30)

cmd = """
cd /opt/telegramforward

# Update env
sed -i 's/OLLAMA_VISION_MODEL=.*/OLLAMA_VISION_MODEL=moondream/' .env
grep OLLAMA .env

# Restart backend with env
pm2 delete telegram-backend 2>/dev/null
export $(grep -v '^#' .env | grep -v '^$' | xargs)
pm2 start scripts/uvicorn_reload.py --name telegram-backend --interpreter /opt/telegramforward/venv/bin/python3
sleep 3
pm2 list --no-color | grep telegram

# Verify backend can reach local Ollama
cat /proc/$(pm2 pid telegram-backend)/environ 2>/dev/null | tr '\\0' '\\n' | grep OLLAMA_VISION
"""

stdin, stdout, stderr = ssh.exec_command(cmd, timeout=30)
print(stdout.read().decode())

ssh.close()
print("\n✓ VPS Ollama configured. No laptop tunnel needed.")
