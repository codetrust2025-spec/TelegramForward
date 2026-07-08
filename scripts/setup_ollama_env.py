#!/usr/bin/env python3
"""Configure VPS backend .env for Ollama via reverse SSH tunnel from laptop."""
import paramiko

VPS_HOST = "187.127.169.159"
VPS_USER = "root"
VPS_PASSWORD = "8897870998s@SS"

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
print("Connecting to VPS...")
ssh.connect(VPS_HOST, username=VPS_USER, password=VPS_PASSWORD, timeout=30)

def run(cmd, label=""):
    if label:
        print(f"\n{'─'*50}\n  {label}\n{'─'*50}")
    stdin, stdout, stderr = ssh.exec_command(cmd, timeout=15)
    out = stdout.read().decode().strip()
    err = stderr.read().decode().strip()
    if out: print(out)
    if err and 'warning' not in err.lower(): print(f"  ERR: {err}")
    return out

# Step 1: Add Ollama env vars to .env file (append if not present)
run("""
grep -q 'OLLAMA_BASE_URL' /opt/telegramforward.old/.env && echo 'Already has OLLAMA vars' || cat >> /opt/telegramforward.old/.env << 'EOF'

# Ollama AI vision - via reverse SSH tunnel from laptop
OLLAMA_BASE_URL=http://127.0.0.1:11434
OLLAMA_VISION_MODEL=qwen2.5vl:7b
OLLAMA_BACKUP_VISION_MODEL=
OLLAMA_REASONING_MODEL=qwen2.5:7b
OLLAMA_TIMEOUT=180
EOF
""", "Step 1: Add Ollama env to .env")

# Step 2: Verify .env has the new vars
run("grep OLLAMA /opt/telegramforward.old/.env", "Step 2: Verify env vars")

# Step 3: Restart PM2
run("pm2 restart telegram-backend", "Step 3: Restart backend")

# Step 4: Check if tunnel is active (will fail if laptop hasn't started tunnel yet)
run("curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1:11434/api/tags 2>/dev/null || echo 'Tunnel not active yet'", "Step 4: Check tunnel status")

# Step 5: Verify backend is running
run("pm2 list --no-color | grep telegram-backend", "Step 5: Backend status")

ssh.close()
print("\n" + "="*50)
print("""
SETUP COMPLETE.

Now on your LAPTOP, run these commands:

Terminal 1 - Start Ollama:
  ollama pull qwen2.5vl:7b
  ollama run qwen2.5vl:7b

Terminal 2 - Start reverse SSH tunnel:
  ssh -N -R 127.0.0.1:11434:127.0.0.1:11434 root@187.127.169.159

Password: 8897870998s@SS

After tunnel is up, test from VPS:
  curl http://127.0.0.1:11434/api/tags

Then test /submit-slot with an invite screenshot.
When tunnel is closed, fallback OCR will work automatically.
""")
