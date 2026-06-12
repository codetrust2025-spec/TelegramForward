#!/usr/bin/env python3
import os, socket, paramiko, sys
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
PASSWORD = os.environ.get("VPS_PASSWORD", "")
sock = socket.create_connection(("187.127.169.159", 22), timeout=30)
c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(hostname="187.127.169.159", username="root", password=PASSWORD, sock=sock)
cmds = [
    "grep -E 'PORT|UVICORN|8000|5173' /opt/telegramforward.old/.env 2>/dev/null | head -10",
    "grep -rn 'registry' /opt/telegramforward.old/server.py | head -15",
    "curl -s http://127.0.0.1:8000/state 2>/dev/null | python3 -c \"import sys,json; d=json.load(sys.stdin); print('keys', list(d.keys())[:10]); print('running', [(k,v.get('campaign_running'),v.get('forwarding_running')) for k,v in (d.get('account_states') or {}).items() if v.get('campaign_running') or v.get('forwarding_running')][:5])\" 2>/dev/null || curl -s http://127.0.0.1:8080/state 2>/dev/null | head -c 200",
]
for cmd in cmds:
    print("\n---", cmd[:70])
    _, stdout, stderr = c.exec_command(cmd, timeout=30)
    print(stdout.read().decode(errors="replace")[:3000])
c.close()
