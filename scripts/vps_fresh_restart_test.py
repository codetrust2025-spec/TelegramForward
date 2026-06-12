#!/usr/bin/env python3
import socket, paramiko, sys, time
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
PASSWORD = "8897870998s@SS"
sock = socket.create_connection(("187.127.169.159", 22), timeout=30)
c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(hostname="187.127.169.159", username="root", password=PASSWORD, sock=sock)

script = r'''
import json, os, pathlib, urllib.request, http.cookiejar, time
# clear checkpoints
for slot in ["account3","account5","account7","account8","account10"]:
    p = f"/opt/telegramforward.old/data/accounts/{slot}/cycle_checkpoint.json"
    if os.path.exists(p): os.remove(p)
cj = http.cookiejar.CookieJar()
op = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))
def req(m,p,d=None):
    r=urllib.request.Request("http://127.0.0.1:8000"+p,method=m)
    r.add_header("Content-Type","application/json")
    if d: r.data=json.dumps(d).encode()
    with op.open(r,timeout=30) as resp: return json.loads(resp.read())
req("POST","/auth/login",{"username":"admin","password":"734720077743"})
for i in range(1,11):
    try: req("POST",f"/account/account{i}/stop")
    except: pass
print("stopped all")
'''
c.exec_command(f"python3 - <<'PY'\n{script}\nPY", timeout=60)
c.exec_command("pm2 restart telegram-backend --update-env", timeout=60)
time.sleep(12)

start = r'''
import json, urllib.request, http.cookiejar, time
cj = http.cookiejar.CookieJar()
op = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))
def req(m,p,d=None):
    r=urllib.request.Request("http://127.0.0.1:8000"+p,method=m)
    r.add_header("Content-Type","application/json")
    if d: r.data=json.dumps(d).encode()
    with op.open(r,timeout=30) as resp: return json.loads(resp.read())
req("POST","/auth/login",{"username":"admin","password":"734720077743"})
req("POST","/account/account10/start?feature=campaign")
for i in range(12):
    time.sleep(10)
    st = req("GET","/state")
    a = st["account_states"]["account10"]
    c = a["campaign"]
    print(f"t+{(i+1)*10}s health={a.get('health_score')} cycle={c['cycle']} sent={c['success']} skip_other={c.get('skipped_other')} notif={a.get('notification','')[:60]}")
    if c["success"] > 0: break
'''
_, stdout, _ = c.exec_command(f"python3 - <<'PY'\n{start}\nPY", timeout=150)
print(stdout.read().decode())
c.close()
