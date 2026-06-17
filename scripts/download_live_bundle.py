#!/usr/bin/env python3
import os, socket, paramiko, sys
from pathlib import Path

PASSWORD = os.environ.get("VPS_PASSWORD", "")
REMOTE = "/opt/telegramforward/static/assets/app-BkUk1ts9.js"
LOCAL = Path(__file__).resolve().parent.parent / "static" / "assets" / "app-BkUk1ts9.js"

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

sock = socket.create_connection(("187.127.169.159", 22), timeout=30)
c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(hostname="187.127.169.159", username="root", password=PASSWORD, sock=sock)
sftp = c.open_sftp()
LOCAL.parent.mkdir(parents=True, exist_ok=True)
sftp.get(REMOTE, str(LOCAL))
sftp.close()
c.close()

b = LOCAL.read_text(encoding="utf-8")
print(f"Downloaded {LOCAL} ({len(b)} bytes)")
for pat in ["function fy({", "accountsModeFilter:P,onAccountsModeFilterChange:O,hideAccountsModeFilter:!0", "includeShutdownInGrid"]:
    print(f"  {pat}: {'YES' if pat in b else 'NO'}")
