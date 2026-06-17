import os
import paramiko

PWD = os.environ.get("VPS_PASSWORD", "")
path = "/opt/telegramforward/dashboard/src/teleautomation-app.jsx"
c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect("187.127.169.159", username="root", password=PWD, timeout=30)
_, o, _ = c.exec_command(f"grep -n 'function Ek' {path}")
print(o.read().decode())
_, o, _ = c.exec_command(f"grep -n 'function Ek\\|Ek({' {path} | head -5")
print(o.read().decode())
c.close()
