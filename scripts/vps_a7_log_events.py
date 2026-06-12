#!/usr/bin/env python3
import socket, paramiko, sys
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
PASSWORD = "8897870998s@SS"
sock = socket.create_connection(("187.127.169.159", 22), timeout=30)
c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(hostname="187.127.169.159", username="root", password=PASSWORD, sock=sock)
cmd = r'''curl -s -c /tmp/cj -b /tmp/cj -X POST http://127.0.0.1:8000/auth/login -H 'Content-Type: application/json' -d '{"username":"admin","password":"734720077743"}' > /dev/null; curl -s -b /tmp/cj http://127.0.0.1:8000/state | python3 -c "
import json,sys
from collections import Counter
d=json.load(sys.stdin)
logs=d['account_states']['account7'].get('logs',[])
print('total logs', len(logs))
c=Counter(L.get('event') for L in logs)
for ev,n in c.most_common(25):
    print(n, ev)
print('--- last 15 ---')
for L in logs[-15:]:
    print(L.get('event'), L.get('msg','')[:130])
"'''
_, stdout, _ = c.exec_command(cmd, timeout=60)
print(stdout.read().decode(errors="replace"))
c.close()
