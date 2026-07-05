#!/usr/bin/env python3
"""Quick deploy: git pull + pm2 restart on VPS."""
import paramiko, sys

VPS_HOST = "187.127.169.159"
VPS_USER = "root"
VPS_PASSWORD = "REMOVED_VPS_PASSWORD"

cmd = "cd /opt/telegramforward && git fetch origin main && git reset --hard origin/main && pm2 restart telegram-backend"

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
print(f"Connecting to {VPS_HOST}...")
ssh.connect(VPS_HOST, username=VPS_USER, password=VPS_PASSWORD, timeout=30)
print(f"Running: {cmd}")
stdin, stdout, stderr = ssh.exec_command(cmd, timeout=60)
out = stdout.read().decode()
err = stderr.read().decode()
rc = stdout.channel.recv_exit_status()
if out: print(out)
if err: print(err, file=sys.stderr)
ssh.close()
print(f"\nDone (exit code {rc})")
sys.exit(rc)
