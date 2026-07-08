#!/usr/bin/env python3
"""Kill stale SSH tunnel listeners on port 11434 on VPS."""
import paramiko

VPS_HOST = "187.127.169.159"
VPS_USER = "root"
VPS_PASSWORD = "8897870998s@SS"

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
print("Connecting to VPS...")
ssh.connect(VPS_HOST, username=VPS_USER, password=VPS_PASSWORD, timeout=30)

# Check what's using port 11434
stdin, stdout, stderr = ssh.exec_command("ss -tlnp | grep 11434", timeout=10)
out = stdout.read().decode().strip()
print(f"Port 11434 usage: {out or 'free'}")

if out:
    # Kill the process holding the port
    stdin, stdout, stderr = ssh.exec_command("fuser -k 11434/tcp 2>/dev/null; sleep 1; ss -tlnp | grep 11434 || echo 'Port freed'", timeout=10)
    out2 = stdout.read().decode().strip()
    print(f"After kill: {out2}")

ssh.close()
print("\nPort 11434 should be free now. Try the SSH tunnel again.")
