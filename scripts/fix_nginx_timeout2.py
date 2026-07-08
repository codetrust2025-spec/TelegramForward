#!/usr/bin/env python3
"""Increase Nginx proxy timeout from 90s to 300s for AI extraction."""
import paramiko

VPS_HOST = "187.127.169.159"
VPS_USER = "root"
VPS_PASSWORD = "REMOVED_VPS_PASSWORD"

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(VPS_HOST, username=VPS_USER, password=VPS_PASSWORD, timeout=30)

cmd = """
# Increase default proxy_read_timeout from 90s to 300s
sed -i 's/proxy_read_timeout 90s;/proxy_read_timeout 300s;/' /etc/nginx/sites-enabled/telegramforward

# Verify
grep 'proxy_read_timeout' /etc/nginx/sites-enabled/telegramforward

# Test nginx config
nginx -t 2>&1

# Reload nginx
systemctl reload nginx
echo "Nginx reloaded."
"""

stdin, stdout, stderr = ssh.exec_command(cmd, timeout=15)
print(stdout.read().decode())
err = stderr.read().decode()
if err:
    print(err)

ssh.close()
