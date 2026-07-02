"""Upload CSV data file to VPS.

This script:
1. Takes a CSV file path as input
2. Uploads it to the VPS at /opt/telegramforward/data/total_joined_list.csv
3. Verifies the upload succeeded
4. Restarts the backend if needed
"""
import sys
import socket
import paramiko
from pathlib import Path

VPS_HOST = '187.127.169.159'
VPS_USER = 'root'
VPS_PASSWORD = '8897870998s@SS'
VPS_DATA_PATH = '/opt/telegramforward/data/total_joined_list.csv'

def upload_csv(local_csv_path: str):
    """Upload CSV to VPS."""
    local_path = Path(local_csv_path)
    
    if not local_path.exists():
        print(f"❌ Error: File not found: {local_csv_path}")
        return False
    
    file_size_mb = local_path.stat().st_size / (1024 * 1024)
    print(f"📁 Local file: {local_path}")
    print(f"📊 Size: {file_size_mb:.2f} MB")
    
    try:
        # Connect to VPS
        print(f"\n🔌 Connecting to VPS {VPS_HOST}...")
        sock = socket.create_connection((VPS_HOST, 22), timeout=30)
        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        client.connect(VPS_HOST, username=VPS_USER, password=VPS_PASSWORD, sock=sock)
        
        # Upload file via SFTP
        print(f"⬆️  Uploading to {VPS_DATA_PATH}...")
        sftp = client.open_sftp()
        sftp.put(str(local_path), VPS_DATA_PATH)
        sftp.close()
        print("✅ Upload complete")
        
        # Verify upload
        print("\n🔍 Verifying upload...")
        stdin, stdout, stderr = client.exec_command(f"ls -lh {VPS_DATA_PATH}")
        print(stdout.read().decode())
        
        stdin, stdout, stderr = client.exec_command(f"wc -l {VPS_DATA_PATH}")
        line_count = stdout.read().decode().strip()
        print(f"📊 Lines in file: {line_count}")
        
        stdin, stdout, stderr = client.exec_command(f"head -3 {VPS_DATA_PATH}")
        print("First 3 lines:")
        print(stdout.read().decode())
        
        # Check if backend needs restart
        print("\n🔄 Checking backend status...")
        stdin, stdout, stderr = client.exec_command("ps aux | grep uvicorn | grep -v grep")
        backend_process = stdout.read().decode()
        
        if backend_process:
            print("✅ Backend is running")
            print("\n💡 The backend should auto-reload with the new data.")
            print("   If data doesn't appear, you may need to restart it:")
            print("   SSH to VPS and run: systemctl restart telegramforward")
        else:
            print("⚠️  Backend is not running!")
            print("   Start it with: systemctl start telegramforward")
        
        client.close()
        return True
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python scripts/upload_csv_data.py <path_to_csv>")
        print("\nExample:")
        print('  python scripts/upload_csv_data.py "C:\\Users\\codet\\Downloads\\total_joined_list_20260630_0236.csv"')
        sys.exit(1)
    
    csv_path = sys.argv[1]
    success = upload_csv(csv_path)
    sys.exit(0 if success else 1)
