#!/usr/bin/env python3
"""Quick test: verify the /public/slots/extract-invite-ai endpoint is registered."""
import paramiko

VPS_HOST = "187.127.169.159"
VPS_USER = "root"
VPS_PASSWORD = "REMOVED_VPS_PASSWORD"

# Just check if the endpoint responds (even without a file it should give a 422 validation error, not 404)
cmd = "curl -s -o /dev/null -w '%{http_code}' -X POST http://localhost:8000/public/slots/extract-invite-ai"

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(VPS_HOST, username=VPS_USER, password=VPS_PASSWORD, timeout=30)
stdin, stdout, stderr = ssh.exec_command(cmd, timeout=15)
code = stdout.read().decode().strip()
print(f"HTTP status: {code}")
if code == "422":
    print("✓ Endpoint is registered (422 = missing required file field)")
elif code == "404":
    print("✗ Endpoint NOT found")
else:
    print(f"Response code: {code}")
ssh.close()
