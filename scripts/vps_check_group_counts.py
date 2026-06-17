#!/usr/bin/env python3
import json, os, socket, sys
import paramiko
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
PASSWORD = os.environ.get("VPS_PASSWORD", "")
DIAG = '''
import json
from pathlib import Path
import sys
sys.path.insert(0, "/opt/telegramforward.old")
from core.groups_store import groups_readonly_snapshot_for_slot
from core.group_assignment import partition_summary, groups_for_slot
from core.groups_store import load_master_groups

for slot in ["account3", "account8", "account5"]:
    master = load_master_groups()
    part = partition_summary(slot, master)
    snap = groups_readonly_snapshot_for_slot(slot)
    blocked = json.loads(Path(f"/opt/telegramforward.old/data/accounts/{slot}/blocked_groups.json").read_text())
    blen = len(blocked) if isinstance(blocked, list) else len(blocked)
    print(slot, "assigned=", part["assigned_count"], "snapshot=", len(snap), "blocked_file=", blen)
    cm = json.loads(Path(f"/opt/telegramforward.old/data/accounts/{slot}/cycle_metrics_last.json").read_text())
    print("  cycle:", cm.get("success"), cm.get("skipped"), cm.get("groups_total"), "ended", cm.get("ended_at"))
'''
sock = socket.create_connection(("187.127.169.159", 22), timeout=30)
c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(hostname="187.127.169.159", username="root", password=PASSWORD, sock=sock)
sftp = c.open_sftp()
with sftp.open("/tmp/diag6.py", "w") as f:
    f.write(DIAG)
sftp.close()
_, stdout, _ = c.exec_command("cd /opt/telegramforward.old && venv/bin/python /tmp/diag6.py 2>&1", timeout=60)
print(stdout.read().decode())
c.close()
