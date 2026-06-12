#!/usr/bin/env python3
import socket, paramiko, sys
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
PASSWORD = "8897870998s@SS"
sock = socket.create_connection(("187.127.169.159", 22), timeout=30)
c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(hostname="187.127.169.159", username="root", password=PASSWORD, sock=sock)
cmd = """curl -s -c /tmp/cj -b /tmp/cj -X POST http://127.0.0.1:8000/auth/login -H 'Content-Type: application/json' -d '{"username":"admin","password":"734720077743"}' > /dev/null; curl -s -b /tmp/cj http://127.0.0.1:8000/state | python3 -c "import json,sys; d=json.load(sys.stdin); print('keys', list(d.keys())[:20]); print('type accounts', type(d.get('accounts'))); 
if isinstance(d.get('accounts'), dict):
  print('acct keys', list(d['accounts'].keys())[:15])
elif isinstance(d.get('accounts'), list):
  print('acct len', len(d['accounts']))
  if d['accounts']: print('first keys', list(d['accounts'][0].keys())[:20])
for k,v in d.items():
  if k != 'accounts' and k != 'logs':
    print(k, type(v), str(v)[:120])
" """
_, stdout, stderr = c.exec_command(cmd, timeout=60)
print(stdout.read().decode(errors="replace"))
print(stderr.read().decode(errors="replace"))
c.close()
