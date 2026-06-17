#!/usr/bin/env python3
import os, socket, sys, json
import paramiko
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
PASSWORD = os.environ.get("VPS_PASSWORD", "")
SCRIPT = """
import json, sys, urllib.request
sys.path.insert(0, '/opt/telegramforward.old')
from core.dashboard_auth_vps import get_credentials, create_session_token, SESSION_COOKIE

user, pw = get_credentials()
token = create_session_token(user, role='admin')
req = urllib.request.Request('http://127.0.0.1:8000/state')
req.add_header('Cookie', f'{SESSION_COOKIE}={token}')
state = json.loads(urllib.request.urlopen(req, timeout=20).read())
ds = state.get('daily_stats') or {}
pa = ds.get('per_account') or {}
fwd_total = camp_total = 0
print('=== Since reset (daily_stats) ===')
print('window:', ds.get('window'))
rows = []
for slot, row in sorted(pa.items()):
    fp = int(row.get('forward_posts') or 0)
    cp = int(row.get('campaign_posts') or 0)
    fwd_total += fp
    camp_total += cp
    if fp or cp:
        rows.append((slot, fp, cp))
for slot, fp, cp in rows:
    print(f'  {slot}: forward={fp} campaign={cp}')
print(f'FLEET forward posts: {fwd_total}')
print(f'FLEET campaign posts: {camp_total}')
if fwd_total > camp_total:
    print('WINNER: FORWARDING (higher total reach since reset)')
elif camp_total > fwd_total:
    print('WINNER: CAMPAIGN (higher total reach since reset)')
else:
    print('TIE')

print()
print('=== Current tick ===')
fs = ff = cs = cf = 0
for slot, a in (state.get('account_states') or {}).items():
    f = a.get('forwarding') or {}
    c = a.get('campaign') or {}
    fs += int(f.get('success') or 0)
    ff += int(f.get('failed') or 0)
    cs += int(c.get('success') or 0)
    cf += int(c.get('failed') or 0)
print(f'Forwarding: sent={fs} fail={ff}')
print(f'Campaign: sent={cs} fail={cf}')
"""
sock = socket.create_connection(("187.127.169.159", 22), timeout=30)
c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(hostname="187.127.169.159", username="root", password=PASSWORD, sock=sock)
sftp = c.open_sftp()
with sftp.open("/tmp/reach_cmp.py", "w") as f:
    f.write(SCRIPT)
sftp.close()
_, stdout, _ = c.exec_command("/opt/telegramforward.old/venv/bin/python /tmp/reach_cmp.py 2>&1", timeout=45)
print(stdout.read().decode())
c.close()
