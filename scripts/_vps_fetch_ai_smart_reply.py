import os
import sys
from pathlib import Path

import paramiko

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = Path(r"C:\Users\codet\TelegramForward")

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect("187.127.169.159", username="root", password=os.environ.get("VPS_PASSWORD", ""), timeout=30)
sftp = c.open_sftp()
for remote, local in [
    ("/opt/telegramforward/core/ai_smart_reply.py", ROOT / "core" / "ai_smart_reply.py"),
    ("/opt/telegramforward/core/ai_smart_reply_store.py", ROOT / "core" / "ai_smart_reply_store.py"),
    ("/opt/telegramforward/data/ai_smart_reply.json", ROOT / "data" / "ai_smart_reply.json"),
]:
    try:
        sftp.get(remote, str(local))
        print("saved", local.name)
    except OSError as e:
        print("skip", remote, e)
sftp.close()
c.close()
