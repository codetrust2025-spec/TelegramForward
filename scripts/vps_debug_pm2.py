#!/usr/bin/env python3
"""Debug PM2 configuration issue."""
import paramiko
import json

VPS_HOST = '187.127.169.159'
VPS_USER = 'root'
VPS_PASSWORD = 'REMOVED_VPS_PASSWORD'
VPS_PATH = '/opt/telegramforward'

def ssh_command(command: str, timeout: int = 30) -> tuple[str, str, int]:
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
    print("=== PM2 Configuration Debug ===\n")
    
    print("[1] Checking ecosystem file content...")
    out, err, code = ssh_command(f"cat {VPS_PATH}/ecosystem.production.cjs")
    print(out)
    
    print("\n[2] Checking if PM2 can parse the file...")
    out, err, code = ssh_command(f"cd {VPS_PATH} && pm2 prettylist")
    print("PM2 Process List (JSON):")
    print(out[:500])
    
    print("\n[3] Checking what PM2 thinks it's running...")
    out, err, code = ssh_command(f"cd {VPS_PATH} && pm2 describe 0")
    print(out)
    
    print("\n[4] Checking if Python script exists...")
    out, err, code = ssh_command(f"ls -l {VPS_PATH}/scripts/uvicorn_reload.py {VPS_PATH}/venv/bin/python3")
    print(out)
    
    print("\n[5] Try running Python script directly...")
    out, err, code = ssh_command(f"cd {VPS_PATH} && timeout 5 venv/bin/python3 scripts/uvicorn_reload.py 2>&1 || echo 'Script timed out or failed'")
    print(out[:1000])
    
    print("\n[6] Checking PATH variable in PM2 env...")
    out, err, code = ssh_command(f"pm2 show 0 2>&1 | grep -A20 'env:' || echo 'No env found'")
    print(out)

if __name__ == '__main__':
    main()
