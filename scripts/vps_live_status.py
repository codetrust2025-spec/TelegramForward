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
d=json.load(sys.stdin)
for slot in ['account3','account5','account7','account8','account10']:
    a=d['account_states'][slot]
    c=a['campaign']
    print(slot, 'health', a.get('health_score'), 'cycle', c['cycle'], 'sent', c['success'], 'fail', c['failed'], 'status', c['status'], 'cur', (a.get('current_group') or '')[:30], 'notif', (a.get('notification') or '')[:50])
"'''
_, stdout, _ = c.exec_command(cmd, timeout=30)
print(stdout.read().decode())
c.close()
