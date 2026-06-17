#!/usr/bin/env python3
"""Check worker state and force campaign cycles on account3/8."""
import os
import socket
import sys
import time

import paramiko

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
PASSWORD = os.environ.get("VPS_PASSWORD", "")
REMOTE = "/opt/telegramforward.old"

SCRIPT = '''
import asyncio
import json
import time
from pathlib import Path

# Check running workers file
rw = Path("/opt/telegramforward.old/data/.running_workers.json")
print("running_workers:", rw.read_text() if rw.exists() else "missing")

# Read latest cycle timestamps
for slot in ["account3", "account8", "account5"]:
    p = Path(f"/opt/telegramforward.old/data/accounts/{slot}/cycle_metrics_last.json")
    if p.exists():
        cm = json.loads(p.read_text())
        age = time.time() - float(cm.get("ended_at") or 0)
        print(f"{slot} cycle#{cm.get('cycle_number')} success={cm.get('success')} skipped={cm.get('skipped')} age_sec={int(age)}")

async def main():
    import sys
    sys.path.insert(0, "/opt/telegramforward.old")
    from services.account_registry import registry

    for slot in ["account3", "account8"]:
        w = registry.workers.get(slot)
        if not w:
            print(f"{slot}: NO WORKER")
            continue
        st = w.state
        print(f"{slot}: running={st.running} campaign={st.campaign_running} forwarding={st.forwarding_running} "
              f"status={st.campaign_status} cycle={st.campaign_cycle} success={st.campaign_success} "
              f"next_in={st.campaign_next_cycle_in}")
        if not st.campaign_running:
            print(f"  -> starting campaign for {slot}")
            registry.start_account(slot, feature="campaign")

asyncio.run(main())
print("waiting 150s...")
'''

sock = socket.create_connection(("187.127.169.159", 22), timeout=30)
c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(hostname="187.127.169.159", username="root", password=PASSWORD, sock=sock)
sftp = c.open_sftp()
with sftp.open("/tmp/force_campaign.py", "w") as f:
    f.write(SCRIPT + '''
import time
time.sleep(150)
for slot in ["account3", "account8", "account5"]:
    p = __import__("pathlib").Path(f"/opt/telegramforward.old/data/accounts/{slot}/cycle_metrics_last.json")
    if p.exists():
        cm = __import__("json").loads(p.read_text())
        age = time.time() - float(cm.get("ended_at") or 0)
        print(f"AFTER {slot}: success={cm.get('success')} failed={cm.get('failed')} skipped={cm.get('skipped')} age_sec={int(age)}")
''')
sftp.close()

_, stdout, stderr = c.exec_command(
    f"cd {REMOTE} && venv/bin/python /tmp/force_campaign.py 2>&1",
    timeout=200,
)
print(stdout.read().decode("utf-8", errors="replace"))
err = stderr.read().decode("utf-8", errors="replace")
if err:
    print("ERR:", err[:2000])
c.close()
