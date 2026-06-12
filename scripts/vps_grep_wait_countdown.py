#!/usr/bin/env python3
import socket, paramiko, sys
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
PASSWORD = "8897870998s@SS"
sock = socket.create_connection(("187.127.169.159", 22), timeout=30)
c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(hostname="187.127.169.159", username="root", password=PASSWORD, sock=sock)
_, stdout, _ = c.exec_command("grep -n '_wait_countdown' /opt/telegramforward.old/workers/account_worker.py | head -40", timeout=30)
print(stdout.read().decode())
_, stdout, _ = c.exec_command(r'''curl -s -c /tmp/cj -b /tmp/cj -X POST http://127.0.0.1:8000/auth/login -H 'Content-Type: application/json' -d '{"username":"admin","password":"734720077743"}' > /dev/null; curl -s -b /tmp/cj http://127.0.0.1:8000/state | python3 -c "
import json,sys
d=json.load(sys.stdin)
logs=d['account_states']['account7']['logs']
for L in logs[-30:]:
    print(L.get('event'), L.get('msg','')[:120], L.get('fields',{}))
print('notification', d.get('account_states',{}).get('account7',{}))
"''', timeout=30)
print("\n=== logs ===")
print(stdout.read().decode(errors="replace"))
c.close()
