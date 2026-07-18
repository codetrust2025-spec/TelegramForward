"""Check which models are configured and if they're available."""
import paramiko
import os
import sys

sys.stdout.reconfigure(encoding='utf-8', errors='replace')
sys.stderr.reconfigure(encoding='utf-8', errors='replace')

PASSWORD = os.environ.get('VPS_PASSWORD', '8897870998s@SS')

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

try:
    client.connect('187.127.169.159', username='root', password=PASSWORD, timeout=15)
    
    # Check all env vars from PM2 process
    cmd = 'cat /proc/629872/environ 2>/dev/null | tr "\\0" "\\n" | grep -i -E "OLLAMA_MAIL|AI_RECRUITMENT|OLLAMA_VISION|OLLAMA_REASONING|AI_INTERVIEW" || echo "NO_MODEL_ENV"'
    stdin, stdout, stderr = client.exec_command(cmd, timeout=10)
    out = stdout.read().decode('utf-8', errors='replace')
    print("=== MODEL ENV VARS ===")
    print(out)
    
    # Check Ollama models available
    cmd2 = 'curl -s http://localhost:11434/api/tags 2>/dev/null | python3 -c "import json,sys; d=json.load(sys.stdin); [print(m.get(\"name\",\"?\")) for m in d.get(\"models\",[])]" 2>/dev/null || echo "OLLAMA_DOWN"'
    stdin2, stdout2, stderr2 = client.exec_command(cmd2, timeout=10)
    out2 = stdout2.read().decode('utf-8', errors='replace')
    print("\n=== INSTALLED OLLAMA MODELS ===")
    print(out2)
    
    # Check the actual error - get full traceback
    cmd3 = 'grep -B20 "OLLAMA_INTERNAL_ERROR" /root/.pm2/logs/telegram-backend-error.log 2>/dev/null | tail -40 || echo "NO_MATCH"'
    stdin3, stdout3, stderr3 = client.exec_command(cmd3, timeout=10)
    out3 = stdout3.read().decode('utf-8', errors='replace')
    print("\n=== FULL ERROR CONTEXT ===")
    print(out3[:4000])
    
    # Check if there's a more detailed error log
    cmd4 = 'grep -i "traceback\|error\|exception\|fail" /root/.pm2/logs/telegram-backend-error.log 2>/dev/null | grep -i ollama | tail -20 || echo "NO_TRACEBACK"'
    stdin4, stdout4, stderr4 = client.exec_command(cmd4, timeout=10)
    out4 = stdout4.read().decode('utf-8', errors='replace')
    print("\n=== OLLAMA TRACEBACKS ===")
    print(out4[:3000])
    
    # Check the ecosystem config for env vars
    cmd5 = 'cat /root/telegram-forward/ecosystem.production.cjs 2>/dev/null || cat /root/telegram-forward/ecosystem.config.cjs 2>/dev/null || echo "NO_ECOSYSTEM"'
    stdin5, stdout5, stderr5 = client.exec_command(cmd5, timeout=10)
    out5 = stdout5.read().decode('utf-8', errors='replace')
    print("\n=== ECOSYSTEM FULL ===")
    print(out5[:3000])
    
    client.close()
except Exception as e:
    print(f"SSH failed: {e}")