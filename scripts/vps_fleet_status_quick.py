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
print('daily success', d.get('success'), 'failed', d.get('failed'))
for slot in d['account_slots']:
    a=d['account_states'][slot]
    c=a['campaign']; f=a['forwarding']
    if c['running'] or f['running']:
        print(slot, 'camp', c['running'], c['status'], 'c'+str(c['cycle']), 's'+str(c['success']), 'f'+str(c['failed']), '| fwd', f['running'], f['status'], 's'+str(f['success']))
# account7 send logs
logs=[L for L in d['account_states']['account7'].get('logs',[]) if 'SEND' in (L.get('event') or '')]
print('account7 send events', len(logs))
for L in logs[-5:]:
    print(L.get('event'), L.get('msg','')[:120])
"'''
_, stdout, _ = c.exec_command(cmd, timeout=60)
print(stdout.read().decode(errors="replace"))
c.close()
