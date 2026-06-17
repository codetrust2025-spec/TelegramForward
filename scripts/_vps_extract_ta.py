import os
import paramiko

PWD = os.environ.get("VPS_PASSWORD", "")
path = "/opt/telegramforward/dashboard/src/teleautomation-app.jsx"
c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect("187.127.169.159", username="root", password=PWD, timeout=30)
_, o, _ = c.exec_command(f"sed -n '1500,1570p' {path}")
text = o.read().decode("utf-8", errors="replace")
open(r"C:\Users\codet\TelegramForward\ta-snippet.txt", "w", encoding="utf-8").write(text)
print("wrote ta-snippet.txt", len(text))
c.close()
