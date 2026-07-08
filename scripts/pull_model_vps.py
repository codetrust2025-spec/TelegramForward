#!/usr/bin/env python3
"""Pull moondream vision model on VPS."""
import paramiko

VPS_HOST = "187.127.169.159"
VPS_USER = "root"
VPS_PASSWORD = "8897870998s@SS"

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
print("Connecting to VPS...")
ssh.connect(VPS_HOST, username=VPS_USER, password=VPS_PASSWORD, timeout=30)

print("Pulling moondream model (~1.7GB). This may take 2-5 minutes...")
stdin, stdout, stderr = ssh.exec_command("ollama pull moondream 2>&1 | tail -3", timeout=600)
print(stdout.read().decode())

# Update env
print("Updating env to use moondream...")
stdin, stdout, stderr = ssh.exec_command("""
sed -i 's/OLLAMA_VISION_MODEL=.*/OLLAMA_VISION_MODEL=moondream/' /opt/telegramforward.old/.env
grep OLLAMA_VISION /opt/telegramforward.old/.env

# Restart backend
cd /opt/telegramforward
pm2 delete telegram-backend 2>/dev/null
export $(grep -v '^#' .env | grep -v '^$' | xargs)
pm2 start scripts/uvicorn_reload.py --name telegram-backend --interpreter /opt/telegramforward/venv/bin/python3
sleep 3
pm2 list --no-color | grep telegram
""", timeout=30)
print(stdout.read().decode())

# Verify
stdin, stdout, stderr = ssh.exec_command("ollama list", timeout=10)
print("Models:", stdout.read().decode())

ssh.close()
print("\n✓ Done! Ollama with moondream running on VPS. No tunnel needed.")
