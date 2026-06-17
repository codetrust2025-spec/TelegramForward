import os
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
import paramiko

PWD = os.environ.get("VPS_PASSWORD", "")
REMOTE = "/opt/telegramforward"
LOCAL = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FILES = [
    "features/data_room_credentials_store.py",
    "dashboard/src/components/DataRoomPanel.jsx",
    "data/data_room/credentials.json",
]

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect("187.127.169.159", username="root", password=PWD, timeout=30)
sftp = c.open_sftp()
for rel in FILES:
    remote = f"{REMOTE}/{rel.replace(chr(92), '/')}"
    local = os.path.join(LOCAL, rel)
    os.makedirs(os.path.dirname(local), exist_ok=True)
    try:
        sftp.get(remote, local)
        print("fetched", rel)
    except Exception as e:
        print("skip", rel, e)
sftp.close()
_, o, _ = c.exec_command(
    'grep -n "offer_letter" /opt/telegramforward/server.py | head -20'
)
print("server routes:")
print(o.read().decode())
c.close()
