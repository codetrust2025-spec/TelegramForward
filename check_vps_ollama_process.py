"""Check Ollama process status and recent crashes."""
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
    
    # Check if ollama process is running
    cmd = 'ps aux | grep -i ollama | grep -v grep || echo "NO_OLLAMA_PROCESS"'
    stdin, stdout, stderr = client.exec_command(cmd, timeout=10)
    out = stdout.read().decode('utf-8', errors='replace')
    print("=== OLLAMA PROCESS ===")
    print(out)
    
    # Check ollama serve logs
    cmd2 = 'journalctl -u ollama --no-pager -n 30 2>/dev/null || echo "NO_JOURNALCTL"'
    stdin2, stdout2, stderr2 = client.exec_command(cmd2, timeout=10)
    out2 = stdout2.read().decode('utf-8', errors='replace')
    print("\n=== OLLAMA JOURNAL (last 30) ===")
    print(out2[:3000])
    
    # Check if ollama is running manually (not as service)
    cmd3 = 'curl -s --connect-timeout 5 http://localhost:11434/api/tags 2>&1 | head -100 || echo "OLLAMA_UNREACHABLE"'
    stdin3, stdout3, stderr3 = client.exec_command(cmd3, timeout=10)
    out3 = stdout3.read().decode('utf-8', errors='replace')
    print("\n=== OLLAMA API CHECK ===")
    print(out3[:1000])
    
    # Check system resources
    cmd4 = 'free -h; echo "---"; df -h / | tail -1'
    stdin4, stdout4, stderr4 = client.exec_command(cmd4, timeout=10)
    out4 = stdout4.read().decode('utf-8', errors='replace')
    print("\n=== SYSTEM RESOURCES ===")
    print(out4)
    
    # Check the actual error log for the most recent ollama error with more context
    cmd5 = 'grep -B30 "Recruitment email queued for review because AI validation failed" /root/.pm2/logs/telegram-backend-error.log 2>/dev/null | tail -50 || echo "NO_MATCH"'
    stdin5, stdout5, stderr5 = client.exec_command(cmd5, timeout=10)
    out5 = stdout5.read().decode('utf-8', errors='replace')
    print("\n=== DETAILED ERROR CONTEXT (last occurrence) ===")
    print(out5[:4000])
    
    client.close()
except Exception as e:
    print(f"SSH failed: {e}")