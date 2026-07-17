#!/usr/bin/env python3
"""Check if the VPS server is running correctly."""
import paramiko
import time

VPS_HOST = '187.127.169.159'
VPS_USER = 'root'
VPS_PASSWORD = '8897870998s@SS'
VPS_PATH = '/opt/telegramforward'

def ssh_command(command: str, check: bool = False, timeout: int = 30) -> tuple[str, str, int]:
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
    print("=== VPS Server Status Check ===\n")
    
    # Check PM2 list
    print("[1/5] Checking PM2 processes...")
    out, err, code = ssh_command("pm2 list", check=False)
    print(out)
    
    # Check PM2 logs (last 30 lines)
    print("\n[2/5] Checking recent logs...")
    out, err, code = ssh_command("pm2 logs --lines 30 --nostream", check=False)
    print(out)
    
    # Check if port 8000 is listening
    print("\n[3/5] Checking if port 8000 is listening...")
    out, err, code = ssh_command("netstat -tulpn | grep ':8000' || ss -tulpn | grep ':8000' || echo 'Port not listening'", check=False)
    if 'LISTEN' in out or '8000' in out:
        print(f"  ✓ Port 8000 is listening")
        print(out)
    else:
        print(f"  ✗ Port 8000 NOT listening")
        print(out)
    
    # Test API endpoint
    print("\n[4/5] Testing API endpoint...")
    out, err, code = ssh_command("curl -s http://localhost:8000/api/ai-recruitment/config || echo 'API not responding'", check=False)
    if '"status":"ok"' in out or '"enabled"' in out:
        print("  ✓ API responding")
        print(f"  Response: {out[:200]}")
    else:
        print("  ✗ API not responding")
        print(f"  Response: {out}")
    
    # Check Python process
    print("\n[5/5] Checking Python processes...")
    out, err, code = ssh_command("ps aux | grep '[p]ython.*uvicorn' | head -5", check=False)
    if out.strip():
        print("  ✓ Python/uvicorn process running:")
        print(out)
    else:
        print("  ✗ No Python/uvicorn process found")
    
    print("\n=== Status Check Complete ===")

if __name__ == '__main__':
    main()
