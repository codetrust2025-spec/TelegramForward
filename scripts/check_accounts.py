#!/usr/bin/env python3
import json, os, sys
import paramiko
PWD = os.environ.get("VPS_PASSWORD", "")

def ssh(cmd):
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect("187.127.169.159", "root", PWD, timeout=30)
    _, o, _ = c.exec_command(cmd, timeout=60)
    out = o.read().decode("utf-8", errors="replace")
    c.close()
    return out

script = r"""
cd /opt/telegramforward.old && source venv/bin/activate && python3 << 'PY'
import os, json, urllib.request, http.cookiejar
from dotenv import load_dotenv
load_dotenv('.env')
op = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
op.open(urllib.request.Request('http://127.0.0.1:8000/auth/login',
    data=json.dumps({'username': os.getenv('DASHBOARD_USERNAME'), 'password': os.getenv('DASHBOARD_PASSWORD')}).encode(),
    headers={'Content-Type':'application/json'}, method='POST'), timeout=15)
d = json.loads(op.open('http://127.0.0.1:8000/state', timeout=20).read().decode())
info = d.get('account_info') or {}
states = d.get('account_states') or {}
running = d.get('running') or []
for slot in sorted(info.keys()):
    ai = info[slot] or {}
    st = states.get(slot) or {}
    name = ai.get('display_name') or ai.get('name') or ''
    if st.get('running') or slot in running:
        msg_path = f'data/accounts/{slot}/custom_message.txt'
        msg = ''
        try:
            msg = open(f'/opt/telegramforward.old/{msg_path}').read().strip()[:120]
        except OSError:
            try:
                msg = open('/opt/telegramforward.old/data/custom_message.txt').read().strip()[:120]
            except OSError:
                pass
        logs = st.get('logs') or []
        last = ''
        for lg in reversed(logs):
            t = lg.get('summary') or lg.get('msg') or ''
            if t and ('SEND' in t or 'Still' in t or 'POST' in t):
                last = t
                break
        print(f"{slot}|{name}|{ai.get('phone')}|running={st.get('running')}|last={last}|msg={msg.replace(chr(10),' ')}")
PY
"""
if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    print(ssh(script))
