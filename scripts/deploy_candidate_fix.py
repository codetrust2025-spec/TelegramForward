"""Deploy the month filter fix to VPS."""
import socket, paramiko
from pathlib import Path

VPS_HOST = '187.127.169.159'
VPS_USER = 'root'
VPS_PASSWORD = '8897870998s@SS'

local_file = Path(__file__).resolve().parents[1] / "features" / "candidate_store.py"
remote_file = "/opt/telegramforward/features/candidate_store.py"

print(f"📁 Deploying: {local_file.name}")
print(f"📍 To: {remote_file}")

try:
    # Connect
    sock = socket.create_connection((VPS_HOST, 22), timeout=30)
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(VPS_HOST, username=VPS_USER, password=VPS_PASSWORD, sock=sock)
    
    # Backup
    import time
    timestamp = time.strftime('%Y%m%d_%H%M%S')
    backup_path = f'{remote_file}.backup_{timestamp}'
    print(f"\n💾 Creating backup: {backup_path}")
    stdin, stdout, stderr = client.exec_command(f"cp {remote_file} {backup_path}")
    stdout.read()
    
    # Upload
    print(f"⬆️  Uploading file...")
    sftp = client.open_sftp()
    sftp.put(str(local_file), remote_file)
    sftp.close()
    print("✅ Upload complete")
    
    # Restart backend
    print("\n🔄 Restarting backend...")
    stdin, stdout, stderr = client.exec_command("pkill -f uvicorn")
    stdout.read()
    time.sleep(3)
    
    # Check if it restarted
    stdin, stdout, stderr = client.exec_command("ps aux | grep uvicorn | grep -v grep")
    result = stdout.read().decode()
    if result:
        print("✅ Backend restarted successfully")
    else:
        print("⚠️  Backend not running, may need manual start")
    
    print(f"\n✅ Deployment complete!")
    print(f"\n💡 Test the fix:")
    print(f"   1. Hard refresh your dashboard (Ctrl+Shift+R)")
    print(f"   2. Select July 2026 month filter")
    print(f"   3. Select Pavan Kalyan reference")
    print(f"   4. You should see ONLY July entries now")
    
    client.close()

except Exception as e:
    print(f"❌ Error: {e}")
    import traceback
    traceback.print_exc()
