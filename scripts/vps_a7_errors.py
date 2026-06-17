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
for L in d['account_states']['account7'].get('logs',[]):
    if 'error' in (L.get('level') or '').lower() or 'Cycle error' in (L.get('msg') or '') or L.get('event')=='cycle_error':
        print(L)
"'''
_, stdout, _ = c.exec_command(cmd, timeout=30)
print(stdout.read().decode() or "(no error logs in buffer)")
_, stdout, _ = c.exec_command("grep 'account7' /root/.pm2/logs/telegram-backend-out.log | grep -iE 'Cycle error|Unexpected|AttributeError|cycle_error' | tail -10", timeout=30)
print("\npm2:", stdout.read().decode() or "(none)")
c.close()
