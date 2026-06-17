import os
import paramiko

PWD = os.environ.get("VPS_PASSWORD", "")
REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REMOTE = "/opt/telegramforward"

with open(os.path.join(REPO, "scripts", "production_update.sh"), "rb") as f:
    data = f.read().replace(b"\r\n", b"\n").replace(b"\r", b"\n")

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect("187.127.169.159", username="root", password=PWD, timeout=30)
sftp = c.open_sftp()
with sftp.open(f"{REMOTE}/scripts/production_update.sh", "w") as f:
    f.write(data)
sftp.close()
_, o, _ = c.exec_command(f"file {REMOTE}/scripts/production_update.sh", timeout=15)
print(o.read().decode())
c.close()
print("uploaded production_update.sh (LF)")
