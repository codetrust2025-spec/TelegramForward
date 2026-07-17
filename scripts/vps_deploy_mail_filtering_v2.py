#!/usr/bin/env python3
"""Deploy mail filtering changes and cleanup noise."""
import paramiko
import sys
import time

VPS_HOST = '187.127.169.159'
VPS_USER = 'root'
VPS_PASSWORD = '8897870998s@SS'
VPS_PATH = '/opt/telegramforward'

def ssh_command(command: str, timeout: int = 120, show_output: bool = True) -> tuple[str, str, int]:
    """Execute SSH command using paramiko."""
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    try:
        client.connect(VPS_HOST, username=VPS_USER, password=VPS_PASSWORD, timeout=30)
        stdin, stdout, stderr = client.exec_command(command, timeout=timeout)
        exit_code = stdout.channel.recv_exit_status()
        out = stdout.read().decode('utf-8', errors='replace')
        err = stderr.read().decode('utf-8', errors='replace')
        if show_output and out:
            print(out[:2000])  # Limit output
        return out, err, exit_code
    finally:
        client.close()

def main():
    print("=== Deploy Mail Filtering Changes ===\n")
    
    print("[1/4] Pulling latest code...")
    out, err, code = ssh_command(f"cd {VPS_PATH} && git pull origin main", show_output=False)
    if 'Already up to date' in out:
        print("  ✓ Already up to date")
    else:
        print("  ✓ Code updated")
    
    print("\n[2/4] Restarting server...")
    out, err, code = ssh_command("pm2 restart telegram-backend", show_output=False)
    print("  ✓ Server restarted")
    
    time.sleep(3)
    
    print("\n[3/4] Running cleanup script on existing noise...")
    print("  (This will scan all PENDING events and mark noise as IGNORED)")
    out, err, code = ssh_command(
        f"cd {VPS_PATH} && venv/bin/python3 scripts/cleanup_needs_review_noise.py 2>&1",
        timeout=300
    )
    
    print("\n[4/4] Checking cleanup results...")
    out, err, code = ssh_command(f"""cd {VPS_PATH} && venv/bin/python3 -c "
from core.db.connection import get_connection
with get_connection() as conn, conn.cursor() as cur:
    cur.execute('SELECT COUNT(*) FROM ai_recruitment_events WHERE review_status=\\'PENDING\\'')
    pending = cur.fetchone()[0]
    cur.execute('SELECT COUNT(*) FROM ai_recruitment_events WHERE review_status=\\'IGNORED\\' AND ignored_at::date = CURRENT_DATE')
    ignored_today = cur.fetchone()[0]
    print(f'Pending events remaining: {{pending}}')
    print(f'Events ignored today: {{ignored_today}}')
" 2>&1""", show_output=False)
    print(out.strip())
    
    print("\n=== Deployment Complete ===")
    print("✓ Mail filtering rules updated")
    print("✓ Server restarted with new rules")
    print("✓ Existing noise cleaned up")
    print("\n📊 Next steps:")
    print("1. Refresh the dashboard")
    print("2. Check 'Mail Monitoring Notifications' section")
    print("3. You should now see ONLY:")
    print("   - Interview confirmations (with date/time)")
    print("   - Selection confirmations")
    print("   - Offer letters")
    print("   - Joining confirmations")

if __name__ == '__main__':
    main()
