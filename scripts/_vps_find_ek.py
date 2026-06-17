import os
import paramiko

PWD = os.environ.get("VPS_PASSWORD", "")
c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect("187.127.169.159", username="root", password=PWD, timeout=30)
_, o, _ = c.exec_command("grep -n 'function Ek' /opt/telegramforward/dashboard/src/teleautomation-app.jsx")
print("lines:", o.read().decode())
_, o, _ = c.exec_command("grep -n 'function Nk\\|function Ek\\|acctRunning' /opt/telegramforward/dashboard/src/teleautomation-app.jsx | head -20")
print(o.read().decode()[:3000])
c.close()
