#!/usr/bin/env python3
"""Run the cleanup script on VPS to clear existing noise."""
import paramiko

VPS_HOST = '187.127.169.159'
VPS_USER = 'root'
VPS_PASSWORD = 'REMOVED_VPS_PASSWORD'
VPS_PATH = '/opt/telegramforward'

def main():
    print("=== Running Cleanup on VPS ===\n")
    
    print("[1/3] Pulling latest code...")
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(VPS_HOST, username=VPS_USER, password=VPS_PASSWORD, timeout=30)
    
    stdin, stdout, stderr = client.exec_command(f"cd {VPS_PATH} && git pull origin main", timeout=60)
    stdout.channel.recv_exit_status()
    out = stdout.read().decode()
    if 'Already up to date' in out:
        print("  ✓ Code already up to date")
    else:
        print("  ✓ Code updated")
    
    print("\n[2/3] Running cleanup script...")
    print("  (Scanning all PENDING events and marking noise as IGNORED)\n")
    
    stdin, stdout, stderr = client.exec_command(
        f"cd {VPS_PATH} && venv/bin/python3 scripts/cleanup_needs_review_noise.py",
        timeout=300
    )
    
    # Stream output in real-time
    while True:
        line = stdout.readline()
        if not line:
            break
        print(line.rstrip())
    
    exit_code = stdout.channel.recv_exit_status()
    
    if exit_code != 0:
        err = stderr.read().decode()
        print(f"\nError: {err}")
    
    print("\n[3/3] Checking results...")
    stdin, stdout, stderr = client.exec_command(f"""cd {VPS_PATH} && venv/bin/python3 -c "
from dotenv import load_dotenv
from pathlib import Path
load_dotenv()
from core.db.connection import get_connection
with get_connection() as conn, conn.cursor() as cur:
    cur.execute('SELECT COUNT(*) FROM ai_recruitment_events WHERE review_status=\\'PENDING\\'')
    pending = cur.fetchone()[0]
    cur.execute('SELECT COUNT(*) FROM ai_recruitment_events WHERE review_status=\\'IGNORED\\'')
    ignored_total = cur.fetchone()[0]
    print(f'✓ Pending events now: {{pending}}')
    print(f'✓ Total ignored events: {{ignored_total}}')
"
""", timeout=60)
    stdout.channel.recv_exit_status()
    print(stdout.read().decode())
    
    client.close()
    
    print("\n=== Cleanup Complete ===")
    print("Refresh your dashboard to see the updated list!")

if __name__ == '__main__':
    main()
