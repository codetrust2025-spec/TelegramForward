#!/usr/bin/env python3
"""Check Python environment setup on VPS and identify venv location."""
import paramiko

VPS_HOST = '187.127.169.159'
VPS_USER = 'root'
VPS_PASSWORD = 'REMOVED_VPS_PASSWORD'
VPS_PATH = '/opt/telegramforward'

def ssh_command(command: str) -> tuple[str, str, int]:
    """Execute SSH command using paramiko."""
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
    print("=== VPS Python Environment Check ===\n")
    
    # Check if venv exists
    print("[1/5] Checking for Python virtual environment...")
    stdout, stderr, code = ssh_command('[ -d /opt/telegramforward/venv ] && echo "EXISTS" || echo "NOT_FOUND"')
    venv_exists = 'EXISTS' in stdout
    print(f"  Virtual env: {'✓ Found' if venv_exists else '✗ Not found'}")
    
    # Check Python versions
    print("\n[2/5] Checking Python versions...")
    stdout, stderr, code = ssh_command('python3 --version 2>&1')
    print(f"  System python3: {stdout.strip()}")
    
    if venv_exists:
        stdout, stderr, code = ssh_command('/opt/telegramforward/venv/bin/python3 --version 2>&1')
        print(f"  Venv python3: {stdout.strip()}")
    
    # Check if uvicorn is available
    print("\n[3/5] Checking for uvicorn...")
    stdout, stderr, code = ssh_command('python3 -c "import uvicorn; print(uvicorn.__version__)" 2>&1')
    if code == 0:
        print(f"  System python: ✓ uvicorn {stdout.strip()}")
    else:
        print(f"  System python: ✗ uvicorn not found")
    
    if venv_exists:
        stdout, stderr, code = ssh_command('/opt/telegramforward/venv/bin/python3 -c "import uvicorn; print(uvicorn.__version__)" 2>&1')
        if code == 0:
            print(f"  Venv python: ✓ uvicorn {stdout.strip()}")
        else:
            print(f"  Venv python: ✗ uvicorn not found")
    
    # Check if fastapi is available
    print("\n[4/5] Checking for fastapi...")
    stdout, stderr, code = ssh_command('python3 -c "import fastapi; print(fastapi.__version__)" 2>&1')
    if code == 0:
        print(f"  System python: ✓ fastapi {stdout.strip()}")
    else:
        print(f"  System python: ✗ fastapi not found")
    
    if venv_exists:
        stdout, stderr, code = ssh_command('/opt/telegramforward/venv/bin/python3 -c "import fastapi; print(fastapi.__version__)" 2>&1')
        if code == 0:
            print(f"  Venv python: ✓ fastapi {stdout.strip()}")
        else:
            print(f"  Venv python: ✗ fastapi not found")
    
    # Check current PM2 interpreter
    print("\n[5/5] Checking PM2 configuration...")
    stdout, stderr, code = ssh_command('cd /opt/telegramforward && cat ecosystem.production.cjs 2>&1 | grep interpreter')
    print(f"  Current PM2 interpreter: {stdout.strip()}")
    
    # Recommendations
    print("\n=== Recommendations ===")
    if venv_exists:
        print("✓ Virtual environment exists at /opt/telegramforward/venv/")
        print("→ Update ecosystem.production.cjs to use venv/bin/python3 as interpreter")
    else:
        print("✗ No virtual environment found")
        print("→ Option 1: Create venv and install dependencies")
        print("→ Option 2: Install dependencies to system python3")

if __name__ == '__main__':
    main()
