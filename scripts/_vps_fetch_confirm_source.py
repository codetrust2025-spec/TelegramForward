import os
import paramiko

PWD = os.environ.get("VPS_PASSWORD", "")
c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect("187.127.169.159", username="root", password=PWD, timeout=30)
_, o, _ = c.exec_command(
    "sed -n '1085,1130p' /opt/telegramforward/dashboard/src/teleautomation-app.jsx",
    timeout=30,
)
print(o.read().decode("utf-8", errors="replace"))
_, o, _ = c.exec_command(
    "sed -n '39718,39735p' /opt/telegramforward/dashboard/src/teleautomation-app.jsx",
    timeout=30,
)
print("--- export ---")
print(o.read().decode("utf-8", errors="replace"))
c.close()
