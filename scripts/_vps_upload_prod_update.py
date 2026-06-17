import os
import paramiko

PWD = os.environ.get("VPS_PASSWORD", "")
REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REMOTE = "/opt/telegramforward"
c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect("187.127.169.159", username="root", password=PWD, timeout=30)
sftp = c.open_sftp()
sftp.put(
    os.path.join(REPO, "scripts", "production_update.sh"),
    f"{REMOTE}/scripts/production_update.sh",
)
sftp.put(
    os.path.join(REPO, "scripts", "_patch_confirm.js"),
    f"{REMOTE}/scripts/_patch_confirm.js",
)
sftp.close()
c.close()
print("uploaded production_update.sh + _patch_confirm.js")
