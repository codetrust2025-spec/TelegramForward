import os
import paramiko

PWD = os.environ["VPS_PASSWORD"]
c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect("187.127.169.159", username="root", password=PWD, timeout=30)
cmds = [
    "grep -n resume /opt/telegramforward/server.py | head -25",
    "ls -la /opt/telegramforward/data/candidates_resumes/7a6a68d247/ 2>&1 | head -10",
    "find /opt/telegramforward/data/candidates_resumes -type f 2>/dev/null | head -15",
    "python3 -c \"import json; d=json.load(open('/opt/telegramforward/data/candidates.json')); r=next((x for x in d.get('candidates',[]) if x.get('id')=='7a6a68d247'),None); print(r.get('name') if r else 'no row'); print(r.get('resumes') if r else '')\"",
]
for cmd in cmds:
    print("===", cmd[:100])
    _, o, _ = c.exec_command(cmd)
    print(o.read().decode("utf-8", errors="replace")[:1500])
c.close()
