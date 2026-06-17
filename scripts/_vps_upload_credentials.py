import os
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
import paramiko

PWD = os.environ.get("VPS_PASSWORD", "")
LOCAL = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "data_room", "credentials.json")
REMOTE = "/opt/telegramforward/data/data_room/credentials.json"

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect("187.127.169.159", username="root", password=PWD, timeout=30)
sftp = c.open_sftp()
sftp.put(LOCAL, REMOTE)
sftp.close()
print("Uploaded credentials.json")
c.close()
