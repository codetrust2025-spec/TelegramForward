import os
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
import paramiko

PWD = os.environ.get("VPS_PASSWORD", "")
REMOTE = "/opt/telegramforward/server.py"
LOCAL = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "server_vps_snippet.txt")

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect("187.127.169.159", username="root", password=PWD, timeout=30)
_, o, _ = c.exec_command("sed -n '3180,3280p' /opt/telegramforward/server.py")
with open(LOCAL, "w", encoding="utf-8") as f:
    f.write(o.read().decode("utf-8", "replace"))
print("wrote", LOCAL)
c.close()
