#!/usr/bin/env python3
"""Compare backup vs current candidates.json to find lost slots."""
import socket, paramiko, sys
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HOST, USER, PWD = "187.127.169.159", "root", "REMOVED_VPS_PASSWORD"

sock = socket.create_connection((HOST, 22), 30)
c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(HOST, username=USER, password=PWD, sock=sock)

script = r"""
python3 -c "
import json

# Load backup (from before the fix deployment)
with open('/opt/telegramforward.old/data/candidates.json.backup_20260702_190852') as f:
    backup = json.load(f)

# Load current
with open('/opt/telegramforward.old/data/candidates.json') as f:
    current = json.load(f)

backup_candidates = backup.get('candidates', [])
current_candidates = current.get('candidates', [])

print(f'Backup: {len(backup_candidates)} candidates')
print(f'Current: {len(current_candidates)} candidates')

# Find confirmed slots in backup
backup_slots = [c for c in backup_candidates if c.get('slot_confirmed')]
current_slots = [c for c in current_candidates if c.get('slot_confirmed')]
print(f'Backup confirmed slots: {len(backup_slots)}')
print(f'Current confirmed slots: {len(current_slots)}')

# Find slots after June 18 in backup
backup_after = [c for c in backup_slots if (c.get('date','') or '') > '2026-06-18']
current_after = [c for c in current_slots if (c.get('date','') or '') > '2026-06-18']
print(f'Backup slots after Jun 18: {len(backup_after)}')
print(f'Current slots after Jun 18: {len(current_after)}')

if backup_after:
    print()
    print('=== SLOTS AFTER JUN 18 IN BACKUP ===')
    for r in sorted(backup_after, key=lambda x: x.get('date','')):
        print(f'  {r.get(\"date\",\"\")} {r.get(\"time\",\"\")} {r.get(\"name\",\"\")} | {r.get(\"technology\",\"\")} | {r.get(\"interview_attendee\",\"\")} | {r.get(\"interview_attendance_status\",\"\")}')

# Find IDs in backup but not in current (deleted candidates)
backup_ids = {c.get('id') for c in backup_candidates if c.get('id')}
current_ids = {c.get('id') for c in current_candidates if c.get('id')}
missing = backup_ids - current_ids
if missing:
    print(f'\\nCandidates in backup but NOT in current: {len(missing)}')
    for cid in sorted(missing):
        row = next((c for c in backup_candidates if c.get('id') == cid), {})
        print(f'  {cid}: {row.get(\"name\",\"\")} | date={row.get(\"date\",\"\")} | confirmed={row.get(\"slot_confirmed\")}')
else:
    print('\\nNo candidates missing from current (all IDs present)')

# Find candidates whose date/slot_confirmed changed
changed = []
for br in backup_candidates:
    bid = br.get('id')
    if not bid: continue
    cr = next((c for c in current_candidates if c.get('id') == bid), None)
    if not cr: continue
    if br.get('slot_confirmed') and not cr.get('slot_confirmed'):
        changed.append((br, cr))
    elif br.get('date') != cr.get('date') and br.get('slot_confirmed'):
        changed.append((br, cr))

if changed:
    print(f'\\n=== SLOTS THAT CHANGED (lost confirmation or date) === ({len(changed)})')
    for br, cr in changed[:20]:
        print(f'  {br.get(\"name\",\"\")} | backup: date={br.get(\"date\")} confirmed={br.get(\"slot_confirmed\")} | current: date={cr.get(\"date\")} confirmed={cr.get(\"slot_confirmed\")}')
"
"""

_, stdout, stderr = c.exec_command(script, timeout=30)
print(stdout.read().decode("utf-8", "replace"))
err = stderr.read().decode("utf-8", "replace")
if err:
    print("STDERR:", err[:800])
c.close()
