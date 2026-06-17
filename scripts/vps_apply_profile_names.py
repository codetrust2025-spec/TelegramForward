#!/usr/bin/env python3
import os, socket, paramiko, sys
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

PASSWORD = os.environ.get("VPS_PASSWORD", "")
LOCAL = r"C:\Users\codet\OneDrive\Desktop\Automation\scripts\bulk_set_profile_names.py"
REMOTE = "/opt/telegramforward.old/scripts/bulk_set_profile_names.py"

sock = socket.create_connection(("187.127.169.159", 22), timeout=30)
c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(hostname="187.127.169.159", username="root", password=PASSWORD, sock=sock)
sftp = c.open_sftp()
try:
    sftp.mkdir("/opt/telegramforward.old/scripts")
except Exception:
    pass
sftp.put(LOCAL, REMOTE)
sftp.close()

cmd = "cd /opt/telegramforward.old && PYTHONPATH=. ./venv/bin/python scripts/bulk_set_profile_names.py"
_, stdout, stderr = c.exec_command(cmd, timeout=600)
out = stdout.read().decode(errors="replace")
err = stderr.read().decode(errors="replace")
print(out)
if err.strip():
    print("STDERR:", err)

_, stdout, stderr = c.exec_command("pm2 restart telegram-backend --update-env", timeout=60)
print(stdout.read().decode())
print(stderr.read().decode())

verify = r"""
cd /opt/telegramforward.old && python3 - <<'PY'
import json
from core.config import ACCOUNT_SLOTS
from core.account_info_store import load_account_info
for slot in ACCOUNT_SLOTS:
    info = load_account_info(slot)
    if info and info.get('phone'):
        print(slot, '->', info.get('display_name') or info.get('name'))
PY
"""
_, stdout, _ = c.exec_command(verify, timeout=60)
print("\n=== VERIFIED ===")
print(stdout.read().decode(errors="replace"))
c.close()
print("Done")
