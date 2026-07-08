#!/usr/bin/env python3
"""Remove moondream from VPS and clean up. Keep Ollama installed for future use."""
import paramiko

VPS_HOST = "187.127.169.159"
VPS_USER = "root"
VPS_PASSWORD = "REMOVED_VPS_PASSWORD"

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(VPS_HOST, username=VPS_USER, password=VPS_PASSWORD, timeout=30)

cmd = """
# Remove moondream model
ollama rm moondream 2>/dev/null
echo "Moondream removed."

# Show remaining disk
df -h / | tail -1

# Keep Ollama installed but no models (ready for future if VPS is upgraded)
ollama list

# Update env back to qwen2.5vl:7b (for laptop tunnel use)
cd /opt/telegramforward
sed -i 's/OLLAMA_VISION_MODEL=moondream/OLLAMA_VISION_MODEL=qwen2.5vl:7b/' .env
grep OLLAMA_VISION .env

# Restart backend
pm2 delete telegram-backend 2>/dev/null
export $(grep -v '^#' .env | grep -v '^$' | xargs)
pm2 start scripts/uvicorn_reload.py --name telegram-backend --interpreter /opt/telegramforward/venv/bin/python3
sleep 3
pm2 list --no-color | grep telegram
"""

stdin, stdout, stderr = ssh.exec_command(cmd, timeout=30)
print(stdout.read().decode())

ssh.close()
print("\n✓ Moondream removed. Env set back to qwen2.5vl:7b (laptop tunnel mode).")
print("  When laptop tunnel is active → AI extraction works")
print("  When laptop is off → OCR fallback works")
