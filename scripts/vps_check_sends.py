#!/usr/bin/env python3
import json, socket, paramiko, sys
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
PASSWORD = "8897870998s@SS"
sock = socket.create_connection(("187.127.169.159", 22), timeout=30)
c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(hostname="187.127.169.159", username="root", password=PASSWORD, sock=sock)
cmd = r'''curl -s -c /tmp/cj -b /tmp/cj -X POST http://127.0.0.1:8000/auth/login -H 'Content-Type: application/json' -d '{"username":"admin","password":"734720077743"}' > /dev/null; curl -s -b /tmp/cj http://127.0.0.1:8000/state | python3 -c "
import json,sys
d=json.load(sys.stdin)
for slot in ['account7']:
    a=d['account_states'][slot]
    camp=a['campaign']
    print('campaign', json.dumps(camp, indent=2))
    print('notification', a.get('notification',''))
    print('current_group', a.get('current_group',''))
    for L in a.get('logs',[])[-20:]:
        ev=L.get('event','')
        if ev in ('SEND_OK','SEND_FAIL','SEND_SKIP','SKIP','CYCLE_START','CYCLE_END','cycle_end') or 'SEND' in ev:
            print(ev, L.get('msg','')[:150], L.get('fields',{}))
"'''
_, stdout, _ = c.exec_command(cmd, timeout=60)
print(stdout.read().decode(errors="replace"))
c.close()
