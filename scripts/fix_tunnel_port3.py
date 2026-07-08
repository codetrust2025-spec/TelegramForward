#!/usr/bin/env python3
"""Fix port 11434 on VPS — careful version."""
import paramiko, time

VPS_HOST = "187.127.169.159"
VPS_USER = "root"
VPS_PASSWORD = "REMOVED_VPS_PASSWORD"

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
print("Connecting to VPS...")
ssh.connect(VPS_HOST, username=VPS_USER, password=VPS_PASSWORD, timeout=30)

# Single command to kill port 11434, wait, and verify
cmd = "fuser -k 11434/tcp 2>/dev/null; sleep 2; ss -tlnp | grep 11434 || echo 'PORT_FREE'"
stdin, stdout, stderr = ssh.exec_command(cmd, timeout=15)
out = stdout.read().decode().strip()
print(f"Result: {out}")

ssh.close()
print("Done. Now try the SSH tunnel command in your terminal.")
