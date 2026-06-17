import os, sys, paramiko
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
path = "/opt/telegramforward/dashboard/src/teleautomation-app.jsx"
c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect("187.127.169.159", "root", password=os.environ.get("VPS_PASSWORD", ""), timeout=30)
_, o, _ = c.exec_command(f"sed -n '1540,1570p' {path}")
print(o.read().decode())
_, o, _ = c.exec_command(f"sed -n '1520,1545p' {path}")
print("--- sig ---")
print(o.read().decode())
c.close()
