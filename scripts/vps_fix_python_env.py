#!/usr/bin/env python3
"""Fix Python environment on VPS: recreate venv and install all dependencies."""
import paramiko
import sys

VPS_HOST = '187.127.169.159'
VPS_USER = 'root'
VPS_PASSWORD = '8897870998s@SS'
VPS_PATH = '/opt/telegramforward'

def ssh_command(command: str, check: bool = True) -> tuple[str, str, int]:
    """Execute SSH command using paramiko."""
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    try:
        client.connect(VPS_HOST, username=VPS_USER, password=VPS_PASSWORD, timeout=30)
        stdin, stdout, stderr = client.exec_command(command, timeout=600)  # 10 min timeout for pip install
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
    print("=== VPS Python Environment Fix ===\n")
    
    # Step 1: Check what's in the venv directory
    print("[1/6] Checking existing venv directory contents...")
    out, err, code = ssh_command(f"ls -la {VPS_PATH}/venv/ 2>&1 | head -20", check=False)
    print(out)
    
    # Step 2: Remove broken venv
    print("\n[2/6] Removing broken venv...")
    out, err, code = ssh_command(f"rm -rf {VPS_PATH}/venv", check=True)
    print("✓ Removed old venv directory")
    
    # Step 3: Create new venv
    print("\n[3/6] Creating new Python virtual environment...")
    out, err, code = ssh_command(f"cd {VPS_PATH} && python3 -m venv venv")
    print("✓ Created new venv at /opt/telegramforward/venv/")
    
    # Step 4: Upgrade pip in venv
    print("\n[4/6] Upgrading pip in venv...")
    out, err, code = ssh_command(f"cd {VPS_PATH} && venv/bin/python3 -m pip install --upgrade pip")
    print("✓ Pip upgraded")
    
    # Step 5: Install requirements
    print("\n[5/6] Installing Python dependencies from requirements.txt...")
    print("  (This may take 2-3 minutes...)")
    out, err, code = ssh_command(f"cd {VPS_PATH} && venv/bin/python3 -m pip install -r requirements.txt")
    # Show only summary lines
    for line in out.split('\n'):
        if 'Successfully installed' in line or 'Requirement already satisfied' in line or 'error' in line.lower():
            print(f"  {line.strip()}")
    print("✓ Dependencies installed")
    
    # Step 6: Verify installation
    print("\n[6/6] Verifying installation...")
    checks = [
        ("Python version", "venv/bin/python3 --version"),
        ("uvicorn", "venv/bin/python3 -c 'import uvicorn; print(uvicorn.__version__)'"),
        ("fastapi", "venv/bin/python3 -c 'import fastapi; print(fastapi.__version__)'"),
        ("telethon", "venv/bin/python3 -c 'import telethon; print(telethon.__version__)'"),
        ("psycopg2", "venv/bin/python3 -c 'import psycopg2; print(psycopg2.__version__)'"),
    ]
    
    for name, cmd in checks:
        out, err, code = ssh_command(f"cd {VPS_PATH} && {cmd} 2>&1", check=False)
        if code == 0:
            print(f"  ✓ {name}: {out.strip()}")
        else:
            print(f"  ✗ {name}: FAILED - {out.strip()}")
    
    print("\n=== Environment Fix Complete ===")
    print("✓ Virtual environment recreated")
    print("✓ All dependencies installed")
    print("\nNext step: Update PM2 config to use venv/bin/python3")

if __name__ == '__main__':
    main()
