#!/usr/bin/env python3
import json, socket, paramiko, sys
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
PASSWORD = "REMOVED_VPS_PASSWORD"
sock = socket.create_connection(("187.127.169.159", 22), timeout=30)
c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(hostname="187.127.169.159", username="root", password=PASSWORD, sock=sock)
_, stdout, _ = c.exec_command("grep -r 'auth/login\\|session\\|DASHBOARD' /opt/telegramforward.old/api/*.py /opt/telegramforward.old/routes/*.py 2>/dev/null | head -40", timeout=30)
print(stdout.read().decode(errors="replace"))
_, stdout, _ = c.exec_command("curl -s -c /tmp/cj -b /tmp/cj -X POST http://127.0.0.1:8000/auth/login -H 'Content-Type: application/json' -d '{\"username\":\"admin\",\"password\":\"734720077743\"}' ; echo; curl -s -b /tmp/cj http://127.0.0.1:8000/state | python3 -c \"import json,sys; d=json.load(sys.stdin); accts=d.get('accounts',{}); print(json.dumps({k:{kk:accts[k].get(kk) for kk in ['running','campaign_running','status','notification','campaign_cycle','campaign_success','campaign_failed','campaign_my_groups']} for k in ['account3','account5','account7','account8','account10'] if k in accts}, indent=2))\"", timeout=60)
print(stdout.read().decode(errors="replace")[:8000])
c.close()
