"""Check Ollama/AI status on VPS."""
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
    
    # Check Ollama service
    cmd = 'systemctl status ollama 2>/dev/null || echo "NO_OLLAMA_SERVICE"; curl -s http://localhost:11434/api/tags 2>/dev/null | head -200 || echo "OLLAMA_NOT_RUNNING"'
    stdin, stdout, stderr = client.exec_command(cmd, timeout=10)
    out = stdout.read().decode('utf-8', errors='replace')
    print("=== OLLAMA STATUS ===")
    print(out[:2000])
    
    # Check env vars from PM2 process
    cmd2 = 'cat /proc/629872/environ 2>/dev/null | tr "\\0" "\\n" | grep -i -E "AI_|OLLAMA|DATABASE|POSTGRES" || echo "NO_PROC_ENV"'
    stdin2, stdout2, stderr2 = client.exec_command(cmd2, timeout=10)
    out2 = stdout2.read().decode('utf-8', errors='replace')
    print("\n=== PM2 PROCESS ENV (AI/DB) ===")
    print(out2[:2000])
    
    # Check all env vars from PM2 process
    cmd3 = 'cat /proc/629872/environ 2>/dev/null | tr "\\0" "\\n" | grep -i "auto_booking\|interview" || echo "NO_BOOKING_ENV"'
    stdin3, stdout3, stderr3 = client.exec_command(cmd3, timeout=10)
    out3 = stdout3.read().decode('utf-8', errors='replace')
    print("\n=== PM2 PROCESS ENV (BOOKING) ===")
    print(out3[:2000])
    
    # Check for more error context around the OLLAMA_INTERNAL_ERROR
    cmd4 = 'grep -B5 -A10 "OLLAMA_INTERNAL_ERROR" /root/.pm2/logs/telegram-backend-error.log 2>/dev/null | tail -60 || echo "NO_MATCH"'
    stdin4, stdout4, stderr4 = client.exec_command(cmd4, timeout=10)
    out4 = stdout4.read().decode('utf-8', errors='replace')
    print("\n=== OLLAMA ERROR CONTEXT ===")
    print(out4[:3000])
    
    # Check the actual .env or ecosystem env
    cmd5 = 'ls -la /root/telegram-forward/.env 2>/dev/null; ls -la /root/telegram-forward/ecosystem.production.cjs 2>/dev/null; ls -la /root/.env 2>/dev/null; echo "---"; cat /root/telegram-forward/ecosystem.production.cjs 2>/dev/null | grep -A20 "env:" | head -30 || echo "NO_ENV_IN_ECO"'
    stdin5, stdout5, stderr5 = client.exec_command(cmd5, timeout=10)
    out5 = stdout5.read().decode('utf-8', errors='replace')
    print("\n=== ENV FILE CHECK ===")
    print(out5[:2000])
    
    client.close()
except Exception as e:
    print(f"SSH failed: {e}")