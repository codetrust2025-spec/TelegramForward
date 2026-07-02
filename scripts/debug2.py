import socket, paramiko
sock = socket.create_connection(('187.127.169.159', 22), timeout=30)
c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect('187.127.169.159', username='root', password='REMOVED_VPS_PASSWORD', sock=sock)

_, stdout, stderr = c.exec_command("""
cd /opt/telegramforward && /opt/telegramforward/venv/bin/python3 -c "
import sys, os
sys.path.insert(0, '.')
from pathlib import Path
for line in Path('.env').read_text().splitlines():
    if line and not line.startswith('#') and '=' in line:
        k, v = line.split('=', 1)
        os.environ[k.strip()] = v.strip()

from features import candidate_store
candidate_store._load_cache = None
results = candidate_store.list_candidates(month='2026-06', reference='Thrilok')
print(f'Total: {len(results)}')
for r in results[:10]:
    print(f'{r.get(\"name\",\"\"):20} date={r.get(\"date\",\"\")} logged={r.get(\"logged_date\",\"\")}')
"
""", timeout=60)
print(stdout.read().decode())
err = stderr.read().decode()
if err:
    print("ERR:", err[:500])
c.close()
