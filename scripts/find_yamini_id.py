#!/usr/bin/env python3
"""Find all candidate IDs for Yamini Akhil in PG."""
import paramiko

VPS_HOST = "187.127.169.159"
VPS_USER = "root"
VPS_PASSWORD = "8897870998s@SS"

cmd = r"""cd /opt/telegramforward && /opt/telegramforward/venv/bin/python3 -c "
import sys, os
sys.path.insert(0, '.')
from features import candidate_store as cs

data = cs._load(force=True)
rows = data.get('candidates') or []

# Check IDs 9ee52550b8 and 929c692a82
target_ids = ['9ee52550b8', '929c692a82', '076b5e4b93', 'a9869778bb', '140cd07db5', 'eab4b8220e', '217d1db918', 'cfdc394b3c', '314f3a5f9d', '967b7142f1', 'e7f3286f0f', 'c18809add8']
for row in rows:
    if row.get('id') in target_ids:
        print(f'ID {row[\"id\"]}: name={row[\"name\"]!r} phone={row.get(\"phone\")} service_type={row.get(\"service_type\")}')
"
"""

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(VPS_HOST, username=VPS_USER, password=VPS_PASSWORD, timeout=30)
stdin, stdout, stderr = ssh.exec_command(cmd, timeout=30)
print(stdout.read().decode())
err = stderr.read().decode()
if err:
    print("STDERR:", err)
ssh.close()
