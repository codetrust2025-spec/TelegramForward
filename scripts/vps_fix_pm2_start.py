#!/usr/bin/env python3
"""Fix PM2 startup - delete broken process and restart correctly."""
import paramiko
import sys
import time

VPS_HOST = '187.127.169.159'
VPS_USER = 'root'
VPS_PASSWORD = '8897870998s@SS'
VPS_PATH = '/opt/telegramforward'

def ssh_command(command: str, check: bool = True, timeout: int = 60) -> tuple[str, str, int]:
    """Execute SSH command using paramiko."""
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    try:
        client.connect(VPS_HOST, username=VPS_USER, password=VPS_PASSWORD, timeout=30)
        stdin, stdout, stderr = client.exec_command(command, timeout=timeout)
        exit_code = stdout.channel.recv_exit_status()
        out = stdout.read().decode('utf-8', errors='replace')
        err = stderr.read().decode('utf-8', errors='replace')
        if check and exit_code != 0:
            print(f"ERROR: Command failed (exit {exit_code})")
            print(f"Command: {command}")
            print(f"Stdout: {out}")
            print(f"Stderr: {err}")
            sys.exit(1)
        return out, err, exit_code
    finally:
        client.close()

def main():
    print("=== Fix PM2 Startup ===\n")
    
    # Step 1: Kill all PM2 processes
    print("[1/4] Stopping all PM2 processes...")
    out, err, code = ssh_command("pm2 kill", check=False)
    print(out)
    print("  ✓ All PM2 processes killed")
    
    time.sleep(2)
    
    # Step 2: Start using the ecosystem file properly
    print("\n[2/4] Starting server using ecosystem file...")
    # The correct way is to specify the ecosystem file which PM2 will read
    out, err, code = ssh_command(
        f"cd {VPS_PATH} && pm2 start ecosystem.production.cjs",
        timeout=120
    )
    print(out)
    
    # Step 3: Save PM2 state
    print("\n[3/4] Saving PM2 configuration...")
    ssh_command("pm2 save", check=False)
    print("  ✓ PM2 state saved")
    
    time.sleep(5)
    
    # Step 4: Check status
    print("\n[4/4] Checking server status...")
    out, err, code = ssh_command("pm2 list", check=False)
    print(out)
    
    print("\n  Checking logs...")
    out, err, code = ssh_command("pm2 logs --lines 20 --nostream", check=False)
    print(out)
    
    print("\n  Checking port 8000...")
    out, err, code = ssh_command("ss -tulpn | grep ':8000' || echo 'Port not listening yet'", check=False)
    print(out)
    
    print("\n  Testing API...")
    time.sleep(2)
    out, err, code = ssh_command("curl -s http://localhost:8000/api/ai-recruitment/config | head -100 || echo 'API not responding'", check=False)
    if '"status"' in out or 'enabled' in out:
        print("  ✓ API responding correctly")
    else:
        print(f"  Response: {out}")
    
    print("\n=== Fix Complete ===")
    print("Check the logs above to verify the server started correctly")

if __name__ == '__main__':
    main()
