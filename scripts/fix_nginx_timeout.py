#!/usr/bin/env python3
"""Fix Nginx proxy timeout for AI extraction endpoint."""
import paramiko

VPS_HOST = "187.127.169.159"
VPS_USER = "root"
VPS_PASSWORD = "8897870998s@SS"

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(VPS_HOST, username=VPS_USER, password=VPS_PASSWORD, timeout=30)

cmd = """
# Check current nginx config for proxy timeouts
grep -n 'proxy_read_timeout\|proxy_connect_timeout\|proxy_send_timeout' /etc/nginx/sites-enabled/* /etc/nginx/nginx.conf 2>/dev/null | head -10

echo "---"

# Add timeout for the AI endpoint location block
# First check if there's already a location for public/slots
grep -n 'extract-invite-ai\|proxy_read_timeout' /etc/nginx/sites-enabled/teleautomation 2>/dev/null || grep -n 'extract-invite-ai\|proxy_read_timeout' /etc/nginx/sites-enabled/default 2>/dev/null

echo "---"

# Find the nginx config file
ls /etc/nginx/sites-enabled/

echo "---"

# Show the relevant server block
grep -A2 'proxy_pass' /etc/nginx/sites-enabled/* 2>/dev/null | head -20
"""

stdin, stdout, stderr = ssh.exec_command(cmd, timeout=15)
print(stdout.read().decode())

ssh.close()
