#!/usr/bin/env python3
"""Restart the backend server on VPS."""
import paramiko

VPS_HOST = '187.127.169.159'
VPS_USER = 'root'
VPS_PASSWORD = 'REMOVED_VPS_PASSWORD'
VPS_PATH = '/opt/telegramforward'

def run_ssh(command: str) -> tuple[str, str, int]:
    """Execute command on VPS via SSH."""
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    try:
        client.connect(VPS_HOST, username=VPS_USER, password=VPS_PASSWORD, timeout=30)
        stdin, stdout, stderr = client.exec_command(command, timeout=60)
        exit_code = stdout.channel.recv_exit_status()
        out = stdout.read().decode('utf-8', errors='replace')
        err = stderr.read().decode('utf-8', errors='replace')
        return out, err, exit_code
    finally:
        client.close()

def main():
    print("=== Restarting Backend Server ===\n")
    
    # Step 1: Check PM2 status
    print("Step 1: Checking PM2 process manager...")
    out, err, code = run_ssh("which pm2")
    if code == 0:
        print(f"✓ PM2 found at: {out.strip()}")
        
        # Check current status
        out, err, _ = run_ssh("pm2 list")
        print("\nCurrent PM2 processes:")
        print(out)
        
        # Restart using PM2
        print("\nStep 2: Restarting via PM2...")
        out, err, code = run_ssh("pm2 restart all")
        if code == 0:
            print("✓ PM2 restart successful")
            print(out)
        else:
            print(f"⚠ PM2 restart had issues (code {code})")
            print(out)
            print(err)
        
        # Check status again
        print("\nStep 3: Verifying restart...")
        out, err, _ = run_ssh("pm2 list")
        print(out)
        
    else:
        print("⚠ PM2 not found, trying manual python3 start...")
        
        # Fallback: manual start
        out, err, _ = run_ssh("pkill -f 'python.*server.py' 2>/dev/null || true")
        print("✓ Stopped any running server.py processes")
        
        # Need to install dependencies first
        print("\nInstalling Python dependencies...")
        out, err, code = run_ssh(
            f"cd {VPS_PATH} && "
            f"pip3 install --user fastapi uvicorn python-multipart || true"
        )
        if code != 0:
            print(f"Warning: pip install had issues")
        
        print("\nStarting server...")
        out, err, code = run_ssh(
            f"cd {VPS_PATH} && "
            f"nohup python3 server.py > /tmp/telegramforward.log 2>&1 & "
            f"echo $!"
        )
        
        if code == 0 and out.strip():
            pid = out.strip()
            print(f"✓ Server started with PID: {pid}")
        else:
            print(f"⚠ Server start command executed")
    
    print("\n=== Restart Complete ===")
    print("The backend server should now be running.")
    print("Try the 'Connect Gmail' button again in the dashboard.")

if __name__ == '__main__':
    main()
