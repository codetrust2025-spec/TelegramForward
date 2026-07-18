"""Check VPS for interview auto-booking status."""
import paramiko
import os
import sys

sys.stdout.reconfigure(encoding='utf-8', errors='replace')
sys.stderr.reconfigure(encoding='utf-8', errors='replace')

PASSWORD = os.environ.get('VPS_PASSWORD', 'REMOVED_VPS_PASSWORD')

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

try:
    client.connect('187.127.169.159', username='root', password=PASSWORD, timeout=15)
    
    # Check env vars
    cmd = 'grep -i "auto_booking\|interview" /root/telegram-forward/.env 2>/dev/null || echo "NO_ENV_FILE"'
    stdin, stdout, stderr = client.exec_command(cmd, timeout=10)
    out = stdout.read().decode('utf-8', errors='replace')
    err = stderr.read().decode('utf-8', errors='replace')
    print("=== ENV VARS ===")
    print(out)
    if err.strip():
        print("STDERR:", err)
    
    # Check recent logs for interview/booking
    cmd2 = 'tail -300 /root/.pm2/logs/telegram-backend-out.log 2>/dev/null | grep -i -E "interview|auto.book|slot.book|booking|classif" | tail -30 || echo "NO_LOGS"'
    stdin2, stdout2, stderr2 = client.exec_command(cmd2, timeout=10)
    out2 = stdout2.read().decode('utf-8', errors='replace')
    err2 = stderr2.read().decode('utf-8', errors='replace')
    print("\n=== RECENT INTERVIEW/BOKING LOGS ===")
    print(out2)
    if err2.strip():
        print("STDERR:", err2)
    
    # Check PM2 status
    cmd3 = 'pm2 jlist 2>/dev/null | python3 -c "import json,sys; d=json.load(sys.stdin); [print(p.get(\"name\",\"?\"), p.get(\"pm2_env\",{}).get(\"status\",\"?\")) for p in d]" 2>/dev/null || echo "NO_PM2"'
    stdin3, stdout3, stderr3 = client.exec_command(cmd3, timeout=10)
    out3 = stdout3.read().decode('utf-8', errors='replace')
    print("\n=== PM2 STATUS ===")
    print(out3)
    
    client.close()
except Exception as e:
    print(f"SSH failed: {e}")