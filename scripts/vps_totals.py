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
camp_sent=sum(d['account_states'][s]['campaign']['success'] for s in d['account_slots'])
camp_fail=sum(d['account_states'][s]['campaign']['failed'] for s in d['account_slots'])
fwd_sent=sum(d['account_states'][s]['forwarding']['success'] for s in d['account_slots'])
print('Campaign total sent', camp_sent, 'fail', camp_fail)
print('Forwarding tick sent', fwd_sent)
for slot in ['account5','account7','account10']:
    c=d['account_states'][slot]['campaign']
    print(slot, 'sent', c['success'], 'lists', c.get('success_list',[])[:3])
for slot in ['account1','account6','account9']:
    f=d['account_states'][slot]['forwarding']
    if f['running']: print(slot, 'fwd', f['status'], 'sent', f['success'])
"'''
_, stdout, _ = c.exec_command(cmd, timeout=30)
print(stdout.read().decode())
c.close()
