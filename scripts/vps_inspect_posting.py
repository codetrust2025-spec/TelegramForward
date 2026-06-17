#!/usr/bin/env python3
import os, socket, paramiko, sys, json
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
PASSWORD = os.environ.get("VPS_PASSWORD", "")
sock = socket.create_connection(("187.127.169.159", 22), timeout=30)
c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(hostname="187.127.169.159", username="root", password=PASSWORD, sock=sock)

script = r'''
import json, os, glob
from core.config import ACCOUNT_SLOTS
from core.account_info_store import load_account_info
from core.posting_mode import load_posting_mode

for slot in [f"account{i}" for i in range(1, 11)]:
    info = load_account_info(slot)
    if not info or not info.get("phone"):
        continue
    pm = load_posting_mode(slot)
    msg_path = f"/opt/telegramforward.old/data/accounts/{slot}/message.txt"
    msg_preview = ""
    if os.path.isfile(msg_path):
        with open(msg_path, encoding="utf-8") as f:
            msg_preview = f.read()[:80].replace("\n", " ")
    print(json.dumps({
        "slot": slot,
        "display_name": info.get("display_name") or info.get("name"),
        "posting_mode": pm.to_dict(slot) if hasattr(pm, "to_dict") else str(pm),
        "message_preview": msg_preview,
    }, ensure_ascii=False))
'''
cmd = f"cd /opt/telegramforward.old && PYTHONPATH=. ./venv/bin/python - <<'PY'\n{script}\nPY"
_, stdout, stderr = c.exec_command(cmd, timeout=120)
print(stdout.read().decode(errors="replace"))
err = stderr.read().decode(errors="replace")
if err.strip():
    print("ERR:", err)

for cmd in [
    "cat /opt/telegramforward.old/core/posting_mode.py | head -120",
    "cat /opt/telegramforward.old/data/message.txt | head -5",
]:
    print("\n===", cmd[:60], "===")
    _, stdout, _ = c.exec_command(cmd, timeout=30)
    print(stdout.read().decode(errors="replace")[:4000])
c.close()
