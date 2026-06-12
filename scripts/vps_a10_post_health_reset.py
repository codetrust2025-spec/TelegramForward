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
a=d['account_states']['account10']
print('health', a.get('health_score'))
print('camp', a['campaign'])
print('exec unhealthy', (a.get('execution_policy') or {}).get('unhealthy'))
for L in a.get('logs',[]):
    ev=L.get('event') or ''
    msg=L.get('msg','')
    if any(x in ev for x in ['SEND','SKIP','CYCLE_END']) or 'Scheduler' in msg or 'posted' in msg.lower() or 'SEND' in msg:
        print(ev, msg[:140])
"'''
_, stdout, _ = c.exec_command(cmd, timeout=30)
print(stdout.read().decode())
c.exec_command("cat /tmp/cycle_err2.log 2>/dev/null | tail -5", timeout=10)
c.close()
