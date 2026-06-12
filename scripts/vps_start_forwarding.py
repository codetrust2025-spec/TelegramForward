#!/usr/bin/env python3
import json, socket, paramiko, sys, time
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
PASSWORD = "REMOVED_VPS_PASSWORD"
sock = socket.create_connection(("187.127.169.159", 22), timeout=30)
c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(hostname="187.127.169.159", username="root", password=PASSWORD, sock=sock)

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
for slot in ["account1","account2","account4","account6","account9"]:
    r=req("POST", f"/account/{slot}/start?feature=forwarding")
    print(slot, "forward start ok")
    time.sleep(1)
st=req("GET","/state")
for slot in ["account1","account2","account4","account6","account9"]:
    f=st["account_states"][slot]["forwarding"]
    print(slot, "fwd running=", f["running"], "status=", f["status"], "notif=", st["account_states"][slot].get("notification","")[:50])
'''
_, stdout, _ = c.exec_command(f"python3 - <<'PY'\n{start}\nPY", timeout=60)
print(stdout.read().decode())

# check account3 why 0 sends
cmd = r'''curl -s -c /tmp/cj -b /tmp/cj -X POST http://127.0.0.1:8000/auth/login -H 'Content-Type: application/json' -d '{"username":"admin","password":"734720077743"}' > /dev/null; curl -s -b /tmp/cj http://127.0.0.1:8000/state | python3 -c "
import json,sys
for slot in ['account3','account8']:
    a=json.load(sys.stdin) if False else None
" 2>/dev/null'''
# simpler
cmd2 = r'''curl -s -c /tmp/cj -b /tmp/cj -X POST http://127.0.0.1:8000/auth/login -H 'Content-Type: application/json' -d '{"username":"admin","password":"734720077743"}' > /dev/null; curl -s -b /tmp/cj http://127.0.0.1:8000/state | python3 -c "
import json,sys
d=json.load(sys.stdin)
for slot in ['account3','account8']:
    a=d['account_states'][slot]
    print(slot, 'health', a.get('health_score'), 'skip', a['campaign'].get('skipped_other'), 'exec', (a.get('execution_policy') or {}).get('unhealthy'))
    for L in a.get('logs',[])[-8:]:
        print(' ', L.get('msg','')[:120])
"'''
_, stdout, _ = c.exec_command(cmd2, timeout=30)
print("\n=== account3/8 ===")
print(stdout.read().decode())
c.close()
