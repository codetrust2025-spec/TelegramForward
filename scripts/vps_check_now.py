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
print('daily success', d.get('success'), 'failed', d.get('failed'), 'total', d.get('total'))
for slot in ['account3','account5','account7','account8','account10']:
    a=d['account_states'][slot]
    c=a['campaign']
    print(f\"{slot}: run={c['running']} st={c['status']} cycle={c['cycle']} sent={c['success']} fail={c['failed']} skip={c.get('skipped_other',0)+c.get('skipped_cooldown',0)} health={a.get('health_score')} cur={a.get('current_group','')[:25]} active={c.get('active_groups')} notif={(a.get('notification') or '')[:55]}\")
    logs=a.get('logs',[])
    events=[L.get('event') for L in logs]
    sends=[L for L in logs if 'SEND' in (L.get('event') or '') or 'send' in (L.get('msg') or '').lower()]
    if sends: print('  last send log:', sends[-1].get('msg','')[:100])
    sched=[L for L in logs if 'Scheduler skip' in (L.get('msg') or '') or L.get('action')=='skipped']
    if sched: print('  skip sample:', sched[-1].get('msg','')[:100])
"'''
_, stdout, _ = c.exec_command(cmd, timeout=60)
print(stdout.read().decode(errors="replace"))
_, stdout, _ = c.exec_command("grep -E 'SEND_|dispatch|Cycle error|AttributeError|account10|account7' /root/.pm2/logs/telegram-backend-out.log 2>/dev/null | tail -25", timeout=30)
print("\n=== pm2 recent ===")
print(stdout.read().decode(errors="replace")[:3000] or "(none)")
c.close()
