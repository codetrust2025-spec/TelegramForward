#!/usr/bin/env python3
"""Fix _process_group_safe to use campaign_runtime for success/failed counters."""
import socket, paramiko, sys, time
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
PASSWORD = "REMOVED_VPS_PASSWORD"
sock = socket.create_connection(("187.127.169.159", 22), timeout=30)
c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(hostname="187.127.169.159", username="root", password=PASSWORD, sock=sock)

fix = """
import pathlib, py_compile
p = pathlib.Path("/opt/telegramforward.old/workers/account_worker.py")
src = p.read_text(encoding="utf-8")
old = '        st = self.state\\n\\n        delay_used: int | None = None\\n\\n        try:\\n\\n            if not st.running:'
new = '        from workers.feature_runtime import campaign_runtime\\n\\n        st = campaign_runtime(self.state)\\n\\n        delay_used: int | None = None\\n\\n        try:\\n\\n            if not st.running:'
# only in _process_group_safe - find unique context
marker = 'Run one atomic group operation'
idx = src.find(marker)
if idx < 0:
    print('marker missing')
else:
    chunk = src[idx:idx+400]
    if 'campaign_runtime(self.state)' in chunk:
        print('already fixed')
    elif 'st = self.state' in chunk:
        src = src[:idx] + src[idx:].replace('st = self.state', 'from workers.feature_runtime import campaign_runtime\\n\\n        st = campaign_runtime(self.state)', 1)
        p.write_text(src, encoding='utf-8')
        print('fixed')
    else:
        print('unexpected', chunk[:200])
py_compile.compile(str(p), doraise=True)
print('syntax ok')
"""
_, stdout, stderr = c.exec_command(f"python3 - <<'PY'\n{fix}\nPY", timeout=30)
print(stdout.read().decode(), stderr.read().decode())

c.exec_command("pm2 restart telegram-backend --update-env", timeout=60)
time.sleep(12)

monitor = """
import json, urllib.request, http.cookiejar, time
cj = http.cookiejar.CookieJar()
op = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))
def req(m,p,d=None):
    r=urllib.request.Request('http://127.0.0.1:8000'+p,method=m)
    r.add_header('Content-Type','application/json')
    if d: r.data=json.dumps(d).encode()
    with op.open(r,timeout=30) as resp: return json.loads(resp.read())
req('POST','/auth/login',{'username':'admin','password':'734720077743'})
for slot in ['account3','account5','account7','account8','account10']:
    try: req('POST', f'/account/{slot}/start?feature=campaign')
    except: pass
for i in range(18):
    time.sleep(10)
    st = req('GET','/state')
    total = sum(st['account_states'][s]['campaign']['success'] for s in ['account3','account5','account7','account8','account10'])
    fail = sum(st['account_states'][s]['campaign']['failed'] for s in ['account3','account5','account7','account8','account10'])
    print(f't+{(i+1)*10}s sent={total} fail={fail}')
    if total > 0:
        print('SUCCESS')
        break
"""
_, stdout, _ = c.exec_command(f"python3 - <<'PY'\n{monitor}\nPY", timeout=220)
print(stdout.read().decode())
c.close()
