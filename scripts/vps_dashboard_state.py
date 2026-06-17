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
ds=d.get('daily_stats',{})
print('DAILY', ds.get('campaign_posts', ds.get('messages_sent')), 'reset success', d.get('success'), 'failed', d.get('failed'))
print('fleet_metrics sample:', {k: v.get('messages_sent') for k,v in list(d.get('fleet_metrics',{}).items())[:3]})
for slot in d['account_slots']:
    a=d['account_states'][slot]
    c=a['campaign']; f=a['forwarding']
    if c['running'] or f['running'] or c['success']>0 or f['success']>0:
        print(f\"{slot}: camp run={c['running']} st={c['status']} sent={c['success']} fail={c['failed']} cycle={c['cycle']} | fwd run={f['running']} st={f['status']} sent={f['success']} fail={f['failed']}\")
    st=d.get('account_status',{}).get(slot,{})
    alerts=[x.get('message','') for x in st.get('alerts',[])]
    if alerts: print(f'  alerts: {alerts[:2]}')
print('forwarding modes:', {k:v.get('mode') for k,v in d.get('posting_modes',{}).items() if v.get('forwarding_enabled')})
"'''
_, stdout, _ = c.exec_command(cmd, timeout=60)
print(stdout.read().decode(errors="replace"))
c.close()
