#!/usr/bin/env python3
import json, socket, paramiko, sys
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
PASSWORD = "REMOVED_VPS_PASSWORD"
sock = socket.create_connection(("187.127.169.159", 22), timeout=30)
c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(hostname="187.127.169.159", username="root", password=PASSWORD, sock=sock)
cmd = r'''curl -s -c /tmp/cj -b /tmp/cj -X POST http://127.0.0.1:8000/auth/login -H 'Content-Type: application/json' -d '{"username":"admin","password":"734720077743"}' > /dev/null; curl -s -b /tmp/cj http://127.0.0.1:8000/state | python3 -c "
import json,sys
d=json.load(sys.stdin)
for slot in ['account7']:
    st=d['account_states'][slot]
    camp=st['campaign']
    info=d['account_info'].get(slot,{})
    status=d['account_status'].get(slot,{})
    print('campaign', json.dumps(camp, indent=2))
    print('phone', info.get('phone'))
    print('account_status', json.dumps(status, indent=2)[:2000])
    logs=st['logs'][-8:]
    for L in logs:
        print(L.get('msg',''), L.get('event',''), L.get('summary',''))
"'''
_, stdout, _ = c.exec_command(cmd, timeout=60)
print(stdout.read().decode(errors="replace"))

# check restriction and posting mode
test = r'''
import sys
sys.path.insert(0,"/opt/telegramforward.old")
from core.join_cycle import restriction_remaining_seconds
from core.posting_mode import load_posting_mode
for slot in ["account7"]:
    print(slot, "restriction", restriction_remaining_seconds(slot))
    print(slot, "mode", load_posting_mode(slot))
'''
_, stdout, _ = c.exec_command(f"cd /opt/telegramforward.old && ./venv/bin/python3 - <<'PY'\n{test}\nPY", timeout=30)
print(stdout.read().decode(errors="replace"))
c.close()
