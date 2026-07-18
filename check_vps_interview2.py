"""Deeper VPS check for interview tracking."""
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
    
    # Find .env file
    cmd = 'find /root -name ".env" -type f 2>/dev/null | head -5'
    stdin, stdout, stderr = client.exec_command(cmd, timeout=10)
    out = stdout.read().decode('utf-8', errors='replace')
    print("=== .env LOCATIONS ===")
    print(out)
    
    # Check if there's an ecosystem file with env
    cmd2 = 'cat /root/telegram-forward/ecosystem.production.cjs 2>/dev/null | head -60 || echo "NO_ECOSYSTEM"'
    stdin2, stdout2, stderr2 = client.exec_command(cmd2, timeout=10)
    out2 = stdout2.read().decode('utf-8', errors='replace')
    print("\n=== ECOSYSTEM CONFIG ===")
    print(out2[:2000])
    
    # Check error log for interview/booking
    cmd3 = 'tail -200 /root/.pm2/logs/telegram-backend-error.log 2>/dev/null | grep -i -E "interview|auto.book|booking|recruitment|mail" | tail -20 || echo "NO_ERROR_LOGS"'
    stdin3, stdout3, stderr3 = client.exec_command(cmd3, timeout=10)
    out3 = stdout3.read().decode('utf-8', errors='replace')
    print("\n=== ERROR LOGS (interview/booking) ===")
    print(out3)
    
    # Check full recent logs (last 50 lines, no filter)
    cmd4 = 'tail -50 /root/.pm2/logs/telegram-backend-out.log 2>/dev/null || echo "NO_OUT_LOG"'
    stdin4, stdout4, stderr4 = client.exec_command(cmd4, timeout=10)
    out4 = stdout4.read().decode('utf-8', errors='replace')
    print("\n=== LAST 50 OUT LOG LINES ===")
    print(out4[-3000:])
    
    # Check pm2 list
    cmd5 = 'pm2 list 2>/dev/null || echo "NO_PM2"'
    stdin5, stdout5, stderr5 = client.exec_command(cmd5, timeout=10)
    out5 = stdout5.read().decode('utf-8', errors='replace')
    print("\n=== PM2 LIST ===")
    print(out5[:2000])
    
    client.close()
except Exception as e:
    print(f"SSH failed: {e}")