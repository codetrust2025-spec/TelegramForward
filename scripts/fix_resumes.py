#!/usr/bin/env python3
"""Fix mismatched resumes — move resumes to the correct candidate based on filename."""
import paramiko

VPS_HOST = "187.127.169.159"
VPS_USER = "root"
VPS_PASSWORD = "8897870998s@SS"

# Script to run on VPS
cmd = r"""cd /opt/telegramforward && /opt/telegramforward/venv/bin/python3 -c "
import sys, json
sys.path.insert(0, '.')
from features import candidate_store as cs

data = cs._load(force=True)
rows = data.get('candidates') or []

print('=== All candidates with resumes ===')
for row in rows:
    resumes = row.get('resumes') or []
    if resumes:
        print(f'  {row[\"name\"]} (id={row[\"id\"]}): {len(resumes)} resume(s)')
        for r in resumes:
            print(f'    - {r.get(\"original_name\") or r.get(\"filename\") or \"unknown\"}')

print()
print('=== Checking for mismatches (filename contains different name) ===')
name_to_id = {}
for row in rows:
    name_to_id[row['name'].strip().lower()] = row['id']

fixes = []
for row in rows:
    resumes = row.get('resumes') or []
    for r in resumes:
        fname = (r.get('original_name') or r.get('filename') or '').lower()
        # Check if filename contains a different candidate's name
        for other_row in rows:
            if other_row['id'] == row['id']:
                continue
            other_name = other_row['name'].strip().lower()
            # Check if filename contains the other person's first name
            parts = other_name.split()
            for part in parts:
                if len(part) >= 4 and part in fname:
                    fixes.append({
                        'resume': r,
                        'current_owner': row['name'],
                        'current_id': row['id'],
                        'likely_owner': other_row['name'],
                        'likely_id': other_row['id'],
                        'filename': r.get('original_name') or r.get('filename'),
                        'match': part,
                    })
                    break

if fixes:
    print(f'Found {len(fixes)} potential mismatch(es):')
    for f in fixes:
        print(f'  File: {f[\"filename\"]}')
        print(f'    Currently under: {f[\"current_owner\"]} ({f[\"current_id\"]})')
        print(f'    Likely belongs to: {f[\"likely_owner\"]} ({f[\"likely_id\"]})')
        print(f'    Match on: \"{f[\"match\"]}\"')
        print()
else:
    print('No mismatches detected.')
"
"""

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
print("Connecting to VPS...")
ssh.connect(VPS_HOST, username=VPS_USER, password=VPS_PASSWORD, timeout=30)
stdin, stdout, stderr = ssh.exec_command(cmd, timeout=30)
out = stdout.read().decode()
err = stderr.read().decode()
print(out)
if err:
    print("STDERR:", err)
ssh.close()
