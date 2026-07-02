"""Deploy both backend and frontend fixes to VPS."""
import socket, paramiko, subprocess
from pathlib import Path

VPS_HOST = '187.127.169.159'
VPS_USER = 'root'
VPS_PASSWORD = '8897870998s@SS'

print("="*70)
print("DEPLOYING FIXES TO VPS")
print("="*70)

# Step 1: Build dashboard
print("\n📦 Step 1: Building dashboard...")
dashboard_path = Path(__file__).resolve().parents[1] / "dashboard"
result = subprocess.run(
    ["node", "node_modules/vite/bin/vite.js", "build"],
    cwd=dashboard_path,
    capture_output=True,
    text=True
)

if result.returncode != 0:
    print("❌ Dashboard build failed!")
    print(result.stderr)
    exit(1)

print("✅ Dashboard built successfully")

# Step 2: Connect to VPS
print("\n🔌 Step 2: Connecting to VPS...")
sock = socket.create_connection((VPS_HOST, 22), timeout=30)
c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(VPS_HOST, username=VPS_USER, password=VPS_PASSWORD, sock=sock)
print("✅ Connected")

# Step 3: Pull latest code from GitHub
print("\n📥 Step 3: Pulling latest code from GitHub...")
_, stdout, stderr = c.exec_command("""
cd /opt/telegramforward
git fetch origin
git reset --hard origin/main
""", timeout=60)
output = stdout.read().decode()
print(output)
errors = stderr.read().decode()
if errors and 'HEAD is now at' not in errors:
    print(f"Warning: {errors}")

# Step 4: Upload built dashboard static files
print("\n📤 Step 4: Uploading dashboard static files...")
static_src = dashboard_path / "dist"
static_dest = "/opt/telegramforward/static"

if not static_src.exists():
    print(f"❌ Build output not found at {static_src}")
    c.close()
    exit(1)

# Backup existing static
_, stdout4, _ = c.exec_command(f"mv {static_dest} {static_dest}.backup_$(date +%Y%m%d_%H%M%S) 2>/dev/null || true", timeout=30)
stdout4.read()

# Create static dir
_, stdout5, _ = c.exec_command(f"mkdir -p {static_dest}", timeout=30)
stdout5.read()

# Upload all files
sftp = c.open_sftp()
for file in static_src.rglob("*"):
    if file.is_file():
        rel_path = file.relative_to(static_src)
        remote_file = f"{static_dest}/{rel_path}".replace("\\", "/")
        
        # Create remote directory if needed
        remote_dir = "/".join(remote_file.split("/")[:-1])
        try:
            sftp.stat(remote_dir)
        except:
            _, mkdir_out, _ = c.exec_command(f"mkdir -p {remote_dir}", timeout=30)
            mkdir_out.read()
        
        sftp.put(str(file), remote_file)

sftp.close()
print("✅ Static files uploaded")

# Step 5: Restart backend
print("\n🔄 Step 5: Restarting backend...")
_, stdout6, _ = c.exec_command("pkill -f uvicorn", timeout=30)
stdout6.read()

import time
time.sleep(3)

_, stdout7, _ = c.exec_command("ps aux | grep uvicorn | grep -v grep", timeout=30)
backend_status = stdout7.read().decode()

if backend_status:
    print("✅ Backend restarted")
else:
    print("⚠️  Backend not running, starting it...")
    _, stdout8, _ = c.exec_command(
        "cd /opt/telegramforward && nohup /opt/telegramforward/venv/bin/python scripts/uvicorn_reload.py --host 0.0.0.0 --port 8000 > logs/backend.log 2>&1 &",
        timeout=30
    )
    stdout8.read()
    time.sleep(2)
    _, stdout9, _ = c.exec_command("ps aux | grep uvicorn | grep -v grep", timeout=30)
    print(stdout9.read().decode())

c.close()

print("\n" + "="*70)
print("✅ DEPLOYMENT COMPLETE!")
print("="*70)
print("""
Fixes deployed:
  ✅ Month filter bug fixed (candidates page)
  ✅ Handler payout totals now match filtered view
  
Test the fixes:
  1. Go to Candidates page
  2. Select "Jul 2026" month filter + "Pavan Kalyan" reference
  3. Should show ONLY July entries
  
  4. Go to Manage handler payouts
  5. Select "Jun 2026" month filter
  6. Header badges should now match the table totals
""")
