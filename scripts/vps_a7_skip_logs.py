#!/usr/bin/env python3
import socket, paramiko, sys
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
PASSWORD = "REMOVED_VPS_PASSWORD"
sock = socket.create_connection(("187.127.169.159", 22), timeout=30)
c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(hostname="187.127.169.159", username="root", password=PASSWORD, sock=sock)
cmd = r'''curl -s -c /tmp/cj -b /tmp/cj -X POST http://127.0.0.1:8000/auth/login -H 'Content-Type: application/json' -d '{"username":"admin","password":"734720077743"}' > /dev/null; curl -s -b /tmp/cj http://127.0.0.1:8000/state | python3 -c "
import json,sys
d=json.load(sys.stdin)
logs=d['account_states']['account7'].get('logs',[])
for L in logs:
    msg=L.get('msg','')
    if any(x in msg.lower() for x in ['skip','scheduler','nothing to post','cycle done','posted','fail']):
        print(msg[:160])
print('---health', d['account_states']['account7'].get('health_score'))
"'''
_, stdout, _ = c.exec_command(cmd, timeout=30)
print(stdout.read().decode())
c.close()
