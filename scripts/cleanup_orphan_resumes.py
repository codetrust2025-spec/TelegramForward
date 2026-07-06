#!/usr/bin/env python3
"""Clean up orphan resume folders on VPS — remove resume files for candidate IDs that don't exist in DB."""
import paramiko

VPS_HOST = "187.127.169.159"
VPS_USER = "root"
VPS_PASSWORD = "REMOVED_VPS_PASSWORD"

cmd = r"""cd /opt/telegramforward && /opt/telegramforward/venv/bin/python3 -c "
import sys, os, shutil
sys.path.insert(0, '.')
from features import candidate_store as cs

RESUMES_DIR = cs.RESUMES_DIR
data = cs._load(force=True)
rows = data.get('candidates') or []
valid_ids = {r['id'] for r in rows if r.get('id')}

print(f'Total candidates in DB: {len(valid_ids)}')
print(f'Resumes dir: {RESUMES_DIR}')

if not os.path.isdir(RESUMES_DIR):
    print('No resumes directory found.')
    sys.exit(0)

folders = os.listdir(RESUMES_DIR)
print(f'Resume folders on disk: {len(folders)}')

orphans = [f for f in folders if f not in valid_ids]
print(f'Orphan folders (ID not in DB): {len(orphans)}')

for folder in orphans:
    path = os.path.join(RESUMES_DIR, folder)
    files = os.listdir(path) if os.path.isdir(path) else []
    print(f'  Removing: {folder}/ ({len(files)} file(s))')
    shutil.rmtree(path, ignore_errors=True)

print(f'Done. Removed {len(orphans)} orphan resume folder(s).')
"
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
