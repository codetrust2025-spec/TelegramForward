#!/usr/bin/env python3
"""Thoroughly fix port 11434 on VPS for reverse tunnel."""
import paramiko, time

VPS_HOST = "187.127.169.159"
VPS_USER = "root"
VPS_PASSWORD = "8897870998s@SS"

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
print("Connecting to VPS...")
ssh.connect(VPS_HOST, username=VPS_USER, password=VPS_PASSWORD, timeout=30)

def run(cmd):
    stdin, stdout, stderr = ssh.exec_command(cmd, timeout=10)
    return stdout.read().decode().strip()

# Kill everything on port 11434
print("Killing all processes on port 11434...")
run("fuser -k 11434/tcp 2>/dev/null")
time.sleep(1)

# Kill all idle SSH sessions that might be holding the port
print("Killing stale SSH forwarding sessions...")
run("pkill -f 'sshd.*notty' 2>/dev/null")
time.sleep(1)

# Verify port is free
result = run("ss -tlnp | grep 11434")
print(f"Port 11434 status: {result or 'FREE'}")

# Enable GatewayPorts in sshd_config if not already set (needed for -R binding)
sshd_conf = run("grep -c 'GatewayPorts' /etc/ssh/sshd_config")
if sshd_conf == "0":
    print("Adding GatewayPorts clientspecified to sshd_config...")
    run("echo 'GatewayPorts clientspecified' >> /etc/ssh/sshd_config")
    run("systemctl reload sshd")
    print("SSH config updated and reloaded.")
else:
    print("GatewayPorts already configured.")

# Final check
result2 = run("ss -tlnp | grep 11434")
print(f"\nFinal port 11434 status: {result2 or 'FREE - ready for tunnel'}")

ssh.close()
print("\nNow enter your password in the terminal where SSH tunnel is waiting.")
