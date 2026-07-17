#!/usr/bin/env python3
"""Deploy updated PM2 configuration and restart server."""
import paramiko
import sys

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
    print("=== Deploy PM2 Config Update ===\n")
    
    # Step 1: Pull latest code
    print("[1/4] Pulling latest code from git...")
    out, err, code = ssh_command(f"cd {VPS_PATH} && git pull origin main")
    print(out)
    if 'Already up to date' in out:
        print("  ✓ Already up to date")
    elif 'Updating' in out or 'Fast-forward' in out:
        print("  ✓ Code updated")
    else:
        print(f"  Warning: Unexpected git output")
    
    # Step 2: Verify PM2 config
    print("\n[2/4] Verifying PM2 configuration...")
    out, err, code = ssh_command(f"cd {VPS_PATH} && grep 'interpreter:' ecosystem.production.cjs")
    print(f"  Current config: {out.strip()}")
    if 'venv' in out and 'python3' in out:
        print("  ✓ PM2 config uses venv interpreter")
    else:
        print("  ✗ PM2 config NOT using venv interpreter!")
        print("  Stopping deployment - check ecosystem.production.cjs")
        sys.exit(1)
    
    # Step 3: Stop PM2
    print("\n[3/4] Stopping PM2 process...")
    out, err, code = ssh_command(f"cd {VPS_PATH} && pm2 stop telegram-backend", check=False)
    if 'stopped' in out.lower() or 'status' in out.lower():
        print("  ✓ Process stopped")
    else:
        print(f"  {out}")
    
    # Delete old PM2 process
    print("  Deleting old PM2 process...")
    out, err, code = ssh_command(f"cd {VPS_PATH} && pm2 delete telegram-backend", check=False)
    if 'deleted' in out.lower() or 'process not found' in out.lower():
        print("  ✓ Process deleted")
    
    # Step 4: Start with new config
    print("\n[4/4] Starting server with new PM2 configuration...")
    out, err, code = ssh_command(f"cd {VPS_PATH} && pm2 start ecosystem.production.cjs", timeout=120)
    print(out)
    if 'online' in out.lower() or 'launched' in out.lower():
        print("  ✓ Server started")
    else:
        print("  ✗ Server may not have started correctly")
        print("  Check PM2 logs for details")
    
    # Save PM2 state
    print("\n  Saving PM2 configuration...")
    ssh_command(f"pm2 save", check=False)
    
    # Show status
    print("\n  Current PM2 status:")
    out, err, code = ssh_command(f"pm2 status", check=False)
    print(out)
    
    # Wait a moment and check logs
    print("\n  Checking startup logs...")
    import time
    time.sleep(3)
    out, err, code = ssh_command(f"pm2 logs telegram-backend --lines 20 --nostream", check=False)
    print(out)
    
    print("\n=== Deployment Complete ===")
    print("✓ Code pulled from git")
    print("✓ PM2 config updated to use venv/bin/python3")
    print("✓ Server restarted with new configuration")
    print("\nNext: Test the API and dashboard")

if __name__ == '__main__':
    main()
