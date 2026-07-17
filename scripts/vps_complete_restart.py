#!/usr/bin/env python3
"""Complete VPS restart with proper environment."""
import paramiko
import time

VPS_HOST = '187.127.169.159'
VPS_USER = 'root'
VPS_PASSWORD = '8897870998s@SS'

def run(cmd):
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(VPS_HOST, username=VPS_USER, password=VPS_PASSWORD, timeout=30)
    stdin, stdout, stderr = c.exec_command(cmd, timeout=60)
    out = stdout.read().decode()
    err = stderr.read().decode()
    code = stdout.channel.recv_exit_status()
    c.close()
    return out, err, code

print("=== Complete VPS Restart ===\n")

print("1. Stop all PM2 processes...")
out, err, _ = run("pm2 delete all")
print(out)

print("\n2. Verify on main branch with latest code...")
out, err, _ = run("cd /opt/telegramforward && git branch && git log --oneline -1")
print(out)

print("\n3. Start server with explicit PYTHONPATH...")
out, err, code = run(
    "cd /opt/telegramforward && "
    "PYTHONPATH=/opt/telegramforward "
    "HOST=0.0.0.0 PORT=8000 NO_RELOAD=1 "
    "nohup python3 scripts/uvicorn_reload.py > /tmp/uvicorn.log 2>&1 & "
    "echo $!"
)
pid = out.strip()
print(f"Started with PID: {pid}")

print("\n4. Wait 5 seconds...")
time.sleep(5)

print("\n5. Test API...")
out, err, code = run("curl -s http://localhost:8000/api/ai-recruitment/config | head -3")
if out.strip():
    print("✓ Server is responding!")
    print(out[:200])
else:
    print("✗ Server not responding. Checking logs...")
    out2, _, _ = run("tail -20 /tmp/uvicorn.log")
    print(out2)

print("\n=== Done ===")
print(f"Server should be running on PID {pid}")
print("Refresh your browser and try again!")
