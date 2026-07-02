#!/usr/bin/env python3
"""Deploy built dashboard static files to VPS."""

import os
import sys
import socket
import paramiko
from pathlib import Path

# VPS connection details
VPS_HOST = "187.127.169.159"
VPS_USER = "root"
VPS_PASSWORD = os.environ.get("VPS_PASSWORD", "8897870998s@SS")
VPS_STATIC_DIR = "/opt/telegramforward.old/static"
LOCAL_STATIC_DIR = Path(__file__).parent.parent / "static"

def connect():
    """Connect to VPS using socket and SSH."""
    sock = socket.create_connection((VPS_HOST, 22), timeout=30)
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(VPS_HOST, username=VPS_USER, password=VPS_PASSWORD, sock=sock)
    return ssh

def upload_directory(sftp, local_dir, remote_dir):
    """Recursively upload directory contents."""
    print(f"📁 Uploading {local_dir} to {remote_dir}")
    
    # Ensure remote directory exists
    try:
        sftp.stat(remote_dir)
    except FileNotFoundError:
        sftp.mkdir(remote_dir)
    
    for item in Path(local_dir).iterdir():
        local_path = str(item)
        remote_path = f"{remote_dir}/{item.name}"
        
        if item.is_dir():
            upload_directory(sftp, local_path, remote_path)
        else:
            print(f"  ↑ {item.name}")
            sftp.put(local_path, remote_path)

def main():
    print("🚀 Deploying dashboard static files to VPS")
    print(f"   Local: {LOCAL_STATIC_DIR}")
    print(f"   Remote: {VPS_STATIC_DIR}")
    
    if not LOCAL_STATIC_DIR.exists():
        print(f"❌ Static directory not found: {LOCAL_STATIC_DIR}")
        print("   Run 'npm run build' in dashboard/ first")
        sys.exit(1)
    
    # Connect to VPS
    print(f"\n🔌 Connecting to {VPS_HOST}...")
    
    try:
        ssh = connect()
        sftp = ssh.open_sftp()
        
        # Backup existing static directory
        print("\n💾 Creating backup...")
        stdin, stdout, stderr = ssh.exec_command(
            f"cp -r {VPS_STATIC_DIR} {VPS_STATIC_DIR}.backup.$(date +%Y%m%d_%H%M%S) 2>/dev/null || true"
        )
        stdout.channel.recv_exit_status()
        
        # Upload new static files
        print("\n📤 Uploading files...")
        upload_directory(sftp, LOCAL_STATIC_DIR, VPS_STATIC_DIR)
        
        # Set permissions
        print("\n🔐 Setting permissions...")
        stdin, stdout, stderr = ssh.exec_command(f"chmod -R 755 {VPS_STATIC_DIR}")
        stdout.channel.recv_exit_status()
        
        print("\n✅ Dashboard static files deployed successfully!")
        print("\n📝 Next steps:")
        print("   1. Hard refresh browser (Ctrl+Shift+R)")
        print("   2. Test: Select 'Jun 2026' in handler payouts")
        print("   3. Verify: Header totals should match table below")
        
        sftp.close()
        ssh.close()
        
    except Exception as e:
        print(f"\n❌ Deployment failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
