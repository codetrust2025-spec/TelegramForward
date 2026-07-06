#!/usr/bin/env python3
"""Find and fix Yamini Akhil resume data via the app's own candidate store."""
import paramiko

VPS_HOST = "187.127.169.159"
VPS_USER = "root"
VPS_PASSWORD = "8897870998s@SS"

# Use pm2 to get the env, then run the fix inline
cmd = """cd /opt/telegramforward && export $(cat .env | grep -v '^#' | xargs) 2>/dev/null; /opt/telegramforward/venv/bin/python3 << 'EOF'
import sys, os
sys.path.insert(0, '.')
os.chdir('/opt/telegramforward')

from features import candidate_store as cs

# Force reload from PG
data = cs._load(force=True)
rows = data.get('candidates') or []

found = []
for row in rows:
    name = (row.get('name') or '').lower()
    if 'yamini' in name or 'akhil' in name:
        found.append(row)

print(f'Found {len(found)} rows with yamini/akhil')
for row in found:
    resumes = row.get('resumes') or []
    print(f'  name={row["name"]!r} id={row["id"]} resumes={len(resumes)}')
    for r in resumes:
        print(f'    -> {r.get("id")}: {r.get("original_name")}')
    if resumes:
        print(f'  CLEARING stale resumes...')
        row['resumes'] = []
        
if any(row.get('resumes') == [] for row in found if (row.get('name') or '').lower().find('yamini') >= 0 or (row.get('name') or '').lower().find('akhil') >= 0):
    # Need to save - but only clear the resumes from these specific rows
    for row in found:
        for i, r in enumerate(rows):
            if r.get('id') == row.get('id'):
                rows[i] = row
                break
    data['candidates'] = rows
    cs._save(data)
    print('Saved.')
else:
    print('No changes needed.')
EOF
"""

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
print("Connecting to VPS...")
ssh.connect(VPS_HOST, username=VPS_USER, password=VPS_PASSWORD, timeout=30)
stdin, stdout, stderr = ssh.exec_command(cmd, timeout=30)
print(stdout.read().decode())
err = stderr.read().decode()
if err:
    print("STDERR:", err)
ssh.close()
