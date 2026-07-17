#!/usr/bin/env python3
"""Final restart with ecosystem.config.cjs."""
import paramiko
import sys
import time

VPS_HOST = '187.127.169.159'
VPS_USER = 'root'
VPS_PASSWORD = '8897870998s@SS'
VPS_PATH = '/opt/telegramforward'

def ssh_command(command: str, timeout: int = 60) -> tuple[str, str, int]:
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
    print("=== Final PM2 Restart ===\n")
    
    print("[1/5] Pulling latest code...")
    out, err, code = ssh_command(f"cd {VPS_PATH} && git pull origin main")
    print(out.strip())
    
    print("\n[2/5] Killing all PM2 processes...")
    out, err, code = ssh_command("pm2 kill")
    print("  ✓ PM2 daemon stopped")
    
    time.sleep(2)
    
    print("\n[3/5] Starting with ecosystem.config.cjs...")
    # Try with just the config filename, PM2 should auto-detect it
    out, err, code = ssh_command(f"cd {VPS_PATH} && pm2 start ecosystem.config.cjs", timeout=120)
    print(out)
    
    ssh_command("pm2 save")
    print("  ✓ PM2 state saved")
    
    time.sleep(5)
    
    print("\n[4/5] Checking status...")
    out, err, code = ssh_command("pm2 list")
    print(out)
    
    print("\n[5/5] Verifying server...")
    out, err, code = ssh_command("pm2 logs --lines 15 --nostream")
    # Only print first 1500 chars to avoid unicode issues
    print(out[:1500])
    
    time.sleep(2)
    print("\n  Testing API...")
    out, err, code = ssh_command("curl -s http://localhost:8000/api/ai-recruitment/config")
    if '"status"' in out:
        print("  ✓✓✓ API IS RESPONDING! ✓✓✓")
        print(f"  {out[:200]}")
    else:
        print("  ✗ API not responding yet")
        print(f"  {out[:200]}")
    
    print("\n=== Restart Complete ===")

if __name__ == '__main__':
    main()
