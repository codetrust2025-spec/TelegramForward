#!/usr/bin/env python3
"""Generate SSH key and install on VPS for passwordless login."""
import os
import paramiko
from pathlib import Path

VPS_HOST = "187.127.169.159"
VPS_USER = "root"
VPS_PASSWORD = "8897870998s@SS"

SSH_DIR = Path.home() / ".ssh"
KEY_FILE = SSH_DIR / "id_rsa"
PUB_FILE = SSH_DIR / "id_rsa.pub"

# Step 1: Generate SSH key if not exists
if not KEY_FILE.exists():
    print("Generating SSH key pair...")
    SSH_DIR.mkdir(exist_ok=True)
    key = paramiko.RSAKey.generate(4096)
    key.write_private_key_file(str(KEY_FILE))
    # Write public key
    pub_key = f"ssh-rsa {key.get_base64()} codet@laptop"
    PUB_FILE.write_text(pub_key + "\n")
    print(f"  Key generated: {KEY_FILE}")
else:
    print(f"  Key already exists: {KEY_FILE}")
    pub_key = PUB_FILE.read_text().strip()

print(f"  Public key: {pub_key[:50]}...")

# Step 2: Install public key on VPS
print(f"\nInstalling key on VPS ({VPS_HOST})...")
ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(VPS_HOST, username=VPS_USER, password=VPS_PASSWORD, timeout=30)

cmd = f"""
mkdir -p ~/.ssh
chmod 700 ~/.ssh
echo '{pub_key}' >> ~/.ssh/authorized_keys
sort -u ~/.ssh/authorized_keys -o ~/.ssh/authorized_keys
chmod 600 ~/.ssh/authorized_keys
echo "Key installed. Total keys: $(wc -l < ~/.ssh/authorized_keys)"
"""

stdin, stdout, stderr = ssh.exec_command(cmd, timeout=10)
print(stdout.read().decode())
ssh.close()

print("\n✓ SSH key authentication configured!")
print("  Now you can SSH without password:")
print(f"  ssh root@{VPS_HOST}")
print(f"\n  Tunnel command (no password needed):")
print(f"  ssh -N -T -o ExitOnForwardFailure=yes -R 127.0.0.1:11434:127.0.0.1:11434 root@{VPS_HOST}")
