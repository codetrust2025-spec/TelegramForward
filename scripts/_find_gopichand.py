import json
import os
import paramiko

PWD = os.environ["VPS_PASSWORD"]
paths = [
    "/opt/telegramforward/data/candidates.json",
    "/opt/telegramforward.old/backups/pre_update_20260603_084737/data/candidates.json",
]
c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect("187.127.169.159", username="root", password=PWD, timeout=30)
for p in paths:
    _, o, _ = c.exec_command(f"python3 -c \"import json; d=json.load(open('{p}')); rows=d.get('candidates',[]); hits=[r for r in rows if 'gopichand' in (r.get('name') or '').lower() or r.get('id')=='7a6a68d247']; print('{p}', len(rows), hits)\"")
    print(o.read().decode("utf-8", errors="replace"))
c.close()
