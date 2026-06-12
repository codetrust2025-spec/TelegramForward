#!/usr/bin/env python3
"""Start campaign workers in-process and verify cycles."""
import os
import socket
import sys

import paramiko

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
PASSWORD = os.environ.get("VPS_PASSWORD", "")
REMOTE = "/opt/telegramforward.old"

SCRIPT = '''
import asyncio
import json
import time
from pathlib import Path

async def main():
    import sys
    sys.path.insert(0, "/opt/telegramforward.old")
    from services.account_manager import manager

    for slot in ["account3", "account5", "account8", "account10"]:
        ok = await manager.start_account(slot, campaign=True)
        print(f"start {slot}: {ok}")

asyncio.run(main())
print("sleep 180s for cycles...")
time.sleep(180)

for slot in ["account3", "account5", "account8", "account10"]:
    p = Path(f"/opt/telegramforward.old/data/accounts/{slot}/cycle_metrics_last.json")
    if p.exists():
        cm = json.loads(p.read_text())
        age = int(time.time() - float(cm.get("ended_at") or 0))
        print(f"{slot}: success={cm.get('success')} failed={cm.get('failed')} skipped={cm.get('skipped')} "
              f"cycle={cm.get('cycle_number')} age={age}s")

rw = Path("/opt/telegramforward.old/data/.running_workers.json")
print("running_workers:", rw.read_text() if rw.exists() else "[]")
'''

sock = socket.create_connection(("187.127.169.159", 22), timeout=30)
c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(hostname="187.127.169.159", username="root", password=PASSWORD, sock=sock)
sftp = c.open_sftp()
with sftp.open("/tmp/start_mgr.py", "w") as f:
    f.write(SCRIPT)
sftp.close()
_, stdout, stderr = c.exec_command(
    f"cd {REMOTE} && venv/bin/python /tmp/start_mgr.py 2>&1",
    timeout=220,
)
print(stdout.read().decode("utf-8", errors="replace"))
err = stderr.read().decode("utf-8", errors="replace")
if err.strip():
    print("ERR:", err[:1500])
c.close()
