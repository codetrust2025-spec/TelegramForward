import json
import os

import paramiko

PWD = os.environ["VPS_PASSWORD"]
c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect("187.127.169.159", username="root", password=PWD, timeout=30)

cmds = [
    "curl -s 'http://127.0.0.1:8000/candidates?month=2026-06' | head -c 500",
    "curl -s 'http://127.0.0.1:8000/candidates/bootstrap?month=2026-06' | head -c 800",
    "grep -n bootstrap /opt/telegramforward/server.py | head -5",
    "python3 -c \"import json; d=json.load(open('/opt/telegramforward/data/candidates.json')); rows=d.get('candidates',[]); print('total',len(rows)); june=sum(1 for r in rows if str(r.get('date',''))[:7]=='2026-06'); print('june',june)\"",
]
for cmd in cmds:
    print("===", cmd[:90])
    _, o, _ = c.exec_command(cmd)
    print(o.read().decode("utf-8", errors="replace")[:900])
c.close()
