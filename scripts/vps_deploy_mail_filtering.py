#!/usr/bin/env python3
"""Deploy mail filtering changes and cleanup noise."""
import paramiko
import sys
import time

VPS_HOST = '187.127.169.159'
VPS_USER = 'root'
VPS_PASSWORD = '8897870998s@SS'
VPS_PATH = '/opt/telegramforward'

def ssh_command(command: str, timeout: int = 120) -> tuple[str, str, int]:
    """Execute SSH command using paramiko."""
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    try:
        client.connect(VPS_HOST, username=VPS_USER, password=VPS_PASSWORD, timeout=30)
        stdin, stdout, stderr = client.exec_command(command, timeout=timeout)
        exit_code = stdout.channel.recv_exit_status()
        out = stdout.read().decode('utf-8', errors='replace')
        err = stderr.read().decode('utf-8', errors='replace')
        return out, err, exit_code
    finally:
        client.close()

def main():
    print("=== Deploy Mail Filtering Changes ===\n")
    
    print("[1/4] Pulling latest code...")
    out, err, code = ssh_command(f"cd {VPS_PATH} && git pull origin main")
    print(out.strip())
    
    print("\n[2/4] Restarting server...")
    out, err, code = ssh_command("pm2 restart telegram-backend")
    print("  ✓ Server restarted")
    
    time.sleep(3)
    
    print("\n[3/4] Running cleanup script on existing noise...")
    out, err, code = ssh_command(
        f"cd {VPS_PATH} && venv/bin/python3 scripts/cleanup_needs_review_noise.py",
        timeout=300
    )
    print(out)
    
    print("\n[4/4] Verifying server status...")
    out, err, code = ssh_command("pm2 list")
    print(out)
    
    print("\n=== Deployment Complete ===")
    print("✓ Code updated")
    print("✓ Server restarted")
    print("✓ Noise cleanup completed")
    print("\nRefresh the dashboard to see the updated 'Needs Review' list")
    print("It should now show only interview slots and job confirmations")

if __name__ == '__main__':
    main()
