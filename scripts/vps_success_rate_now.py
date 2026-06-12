#!/usr/bin/env python3
"""Compute dashboard success rate for campaign vs forwarding tabs."""
import os, socket, sys, json
import paramiko
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
PASSWORD = os.environ.get("VPS_PASSWORD", "")
SCRIPT = r"""
import json, sys, urllib.request
sys.path.insert(0, '/opt/telegramforward.old')
from core.dashboard_auth_vps import get_credentials, create_session_token, SESSION_COOKIE
from core.posting_mode import load_posting_mode

user, pw = get_credentials()
token = create_session_token(user, role='admin')
req = urllib.request.Request('http://127.0.0.1:8000/state')
req.add_header('Cookie', f'{SESSION_COOKIE}={token}')
state = json.loads(urllib.request.urlopen(req, timeout=20).read())
states = state.get('account_states', {})

def mode_for(slot):
    try:
        pm = load_posting_mode(slot)
        return pm.mode or 'campaign'
    except Exception:
        return 'campaign'

def feat(st, mode):
    if mode == 'forwarding':
        f = st.get('forwarding') or {}
        return {
            'success': f.get('success', st.get('forwarding_success', st.get('success', 0))),
            'failed': f.get('failed', st.get('forwarding_failed', st.get('failed', 0))),
            'skipped': f.get('skipped_already_posted', st.get('forwarding_skipped_already_posted', st.get('skipped_already_posted', 0))),
            'cycle': f.get('cycle', 0),
            'status': f.get('status', ''),
            'active': f.get('active_groups', 0),
        }
    f = st.get('campaign') or {}
    return {
        'success': f.get('success', st.get('success', 0)),
        'failed': f.get('failed', st.get('failed', 0)),
        'skipped': f.get('skipped_already_posted', st.get('skipped_already_posted', 0)),
        'cycle': f.get('cycle', 0),
        'status': f.get('status', ''),
        'active': f.get('active_groups', 0),
    }

for tab in ('forwarding', 'campaign'):
    slots = []
    for slot in sorted(states.keys()):
        m = mode_for(slot)
        if tab == 'forwarding' and m in ('forwarding', 'both'):
            slots.append(slot)
        elif tab == 'campaign' and m in ('campaign', 'both'):
            slots.append(slot)
    s = f = sk = 0
    print(f'\n=== {tab.upper()} tab ({len(slots)} accounts) ===')
    for slot in slots:
        st = states.get(slot, {})
        x = feat(st, tab)
        s += x['success']; f += x['failed']; sk += x['skipped']
        print(f"  {slot}: sent={x['success']} fail={x['failed']} skip={x['skipped']} cycle={x['cycle']} status={x['status']}")
    L = s + f
    O = s + f + sk
    if tab == 'forwarding':
        rate = (s / O * 100) if O > 0 else 0.0
        print(f'  Fleet rate (forwarding formula): {s}/{O} = {rate:.1f}%')
    else:
        rate = (s / L * 100) if L > 0 else 0.0
        print(f'  Fleet rate (campaign formula): {s}/{L} = {rate:.1f}%')
    print(f'  NOTE: if sent+fail=0, dashboard shows 0.0%')

print('\n=== Top-level state ===')
print('success=', state.get('success'), 'failed=', state.get('failed'))
"""
sock = socket.create_connection(("187.127.169.159", 22), timeout=30)
c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(hostname="187.127.169.159", username="root", password=PASSWORD, sock=sock)
sftp = c.open_sftp()
with sftp.open("/tmp/rate_calc.py", "w") as f:
    f.write(SCRIPT)
sftp.close()
_, stdout, _ = c.exec_command("/opt/telegramforward.old/venv/bin/python /tmp/rate_calc.py 2>&1", timeout=45)
print(stdout.read().decode())
c.close()
