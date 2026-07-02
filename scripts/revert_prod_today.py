#!/usr/bin/env python3
"""Revert all production changes deployed today (July 2) back to pre-deployment state."""
import socket, paramiko, sys
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HOST, USER, PWD = "187.127.169.159", "root", "REMOVED_VPS_PASSWORD"

sock = socket.create_connection((HOST, 22), 30)
c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(HOST, username=USER, password=PWD, sock=sock)

script = r"""
echo "=== REVERTING candidate_store.py to backup ==="
cd /opt/telegramforward.old/features

# The backup from before today's fix (19:23:38 IST = before our month filter deployment)
if [ -f candidate_store.py.backup_20260702_192338 ]; then
    echo "Restoring candidate_store.py from backup_20260702_192338..."
    cp candidate_store.py candidate_store.py.post_fix_20260702
    cp candidate_store.py.backup_20260702_192338 candidate_store.py
    echo "Done - candidate_store.py reverted"
else
    echo "ERROR: Backup not found!"
fi

echo ""
echo "=== REVERTING candidates.json to backup ==="
cd /opt/telegramforward.old/data
if [ -f candidates.json.backup_20260702_190852 ]; then
    echo "Restoring candidates.json from backup_20260702_190852..."
    cp candidates.json candidates.json.post_fix_20260702
    cp candidates.json.backup_20260702_190852 candidates.json
    echo "Done - candidates.json reverted"
else
    echo "ERROR: candidates.json backup not found!"
fi

echo ""
echo "=== RESTARTING BACKEND ==="
cd /opt/telegramforward.old
pm2 restart telegram-backend 2>&1 | tail -5

echo ""
echo "=== VERIFYING ==="
sleep 2
python3 -c "
import json
with open('/opt/telegramforward.old/data/candidates.json') as f:
    data = json.load(f)
candidates = data.get('candidates', [])
confirmed = [c for c in candidates if c.get('slot_confirmed')]
print(f'Candidates: {len(candidates)}, Confirmed slots: {len(confirmed)}')
dates = sorted(set(c.get('date','')[:10] for c in confirmed if c.get('date','')))
if dates:
    print(f'Slot dates: {dates[0]} to {dates[-1]}')
after_18 = [c for c in confirmed if (c.get('date','') or '') > '2026-06-18']
print(f'Slots after Jun 18: {len(after_18)}')
"
echo ""
echo "=== DONE ==="
"""

_, stdout, stderr = c.exec_command(script, timeout=30)
print(stdout.read().decode("utf-8", "replace"))
err = stderr.read().decode("utf-8", "replace")
if err:
    print("STDERR:", err[:500])
c.close()
