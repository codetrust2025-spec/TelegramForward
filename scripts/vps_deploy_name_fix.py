#!/usr/bin/env python3
import os, socket, paramiko, sys

from _deploy_common import enforce_git_first

enforce_git_first()
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

PASSWORD = os.environ.get("VPS_PASSWORD", "")
LOCAL = r"C:\Users\codet\OneDrive\Desktop\Automation\scripts\ai_smart_reply_vps.py"
REMOTE = "/opt/telegramforward.old/core/ai_smart_reply.py"
REMOTE_LIVE = "/opt/telegramforward/core/ai_smart_reply.py"

sock = socket.create_connection(("187.127.169.159", 22), timeout=30)
c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(hostname="187.127.169.159", username="root", password=PASSWORD, sock=sock)
sftp = c.open_sftp()

for remote in [REMOTE, REMOTE_LIVE]:
    try:
        backup = remote + ".bak_name_fix"
        with sftp.open(remote, "rb") as rf, sftp.open(backup, "wb") as wf:
            wf.write(rf.read())
        sftp.put(LOCAL, remote)
        print(f"Uploaded -> {remote}")
    except Exception as e:
        print(f"Skip {remote}: {e}")

sftp.close()
_, stdout, stderr = c.exec_command("pm2 restart telegram-backend --update-env", timeout=60)
print(stdout.read().decode())
print(stderr.read().decode())
c.close()
print("Done")
