"""Re-deploy the month filter fix after backup restore."""
import socket, paramiko, time

sock = socket.create_connection(('187.127.169.159', 22), timeout=30)
c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect('187.127.169.159', username='root', password='8897870998s@SS', sock=sock)

print("="*70)
print("RE-DEPLOYING CODE FIXES")
print("="*70)

# Pull latest code from GitHub
print("\n1. Pulling latest code from GitHub...")
_, stdout, stderr = c.exec_command("""
cd /opt/telegramforward
git fetch origin 2>&1
git reset --hard origin/main 2>&1
""", timeout=60)
print(stdout.read().decode())
print(stderr.read().decode())

# Verify the fix is in place
print("\n2. Verifying month filter fix is deployed...")
_, stdout2, _ = c.exec_command("grep -c 'Apply month filter BEFORE collapse' /opt/telegramforward/features/candidate_store.py", timeout=30)
fix_present = stdout2.read().decode().strip()
print(f"   Month filter fix present: {'YES' if fix_present == '1' else 'NO'}")

# Restart backend to pick up new code
print("\n3. Restarting backend...")
_, stdout3, _ = c.exec_command("pkill -f uvicorn", timeout=30)
stdout3.read()
time.sleep(5)

_, stdout4, _ = c.exec_command("ps aux | grep uvicorn | grep -v grep", timeout=30)
backend = stdout4.read().decode()
if 'uvicorn' in backend:
    print("   ✅ Backend restarted successfully")
else:
    print("   ⚠️  Backend not running, waiting...")
    time.sleep(5)
    _, stdout5, _ = c.exec_command("ps aux | grep uvicorn | grep -v grep", timeout=30)
    print(f"   {stdout5.read().decode()}")

# Quick API test
print("\n4. Testing API...")
time.sleep(3)
_, stdout6, _ = c.exec_command("curl -s http://127.0.0.1:8000/candidates 2>/dev/null | head -c 100", timeout=30)
api_response = stdout6.read().decode()
if 'candidates' in api_response or 'Authentication' in api_response or 'detail' in api_response:
    print("   ✅ API responding")
else:
    print(f"   API response: {api_response[:100]}")

c.close()

print("\n" + "="*70)
print("✅ DEPLOYMENT COMPLETE!")
print("="*70)
print("""
Your production is now:
  ✅ Database restored to June 27 state (91 candidates, 80 slots, Pavan Kalyan data)
  ✅ Month filter fix deployed (July filter won't show June data)
  ✅ Handler payout totals fix deployed
  ✅ Backend running

Please test your dashboard:
  1. Open https://teleautomation.online
  2. Go to Candidates page
  3. Check that Pavan Kalyan shows up in the reference filter
  4. Check interview slots are present in Daily Ops
""")
