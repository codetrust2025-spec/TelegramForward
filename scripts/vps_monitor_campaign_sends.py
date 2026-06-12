#!/usr/bin/env python3
import json, socket, paramiko, sys, time
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
PASSWORD = "REMOVED_VPS_PASSWORD"
sock = socket.create_connection(("187.127.169.159", 22), timeout=30)
c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(hostname="187.127.169.159", username="root", password=PASSWORD, sock=sock)

remote = r'''
import json, urllib.request, http.cookiejar, time
cj = http.cookiejar.CookieJar()
op = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))
def req(m,p,d=None):
    r=urllib.request.Request("http://127.0.0.1:8000"+p,method=m)
    r.add_header("Content-Type","application/json")
    if d: r.data=json.dumps(d).encode()
    with op.open(r,timeout=30) as resp: return json.loads(resp.read())
req("POST","/auth/login",{"username":"admin","password":"734720077743"})
for slot in ["account7","account8","account10"]:
    req("POST", f"/account/{slot}/start?feature=campaign")
for i in range(18):
    time.sleep(10)
    st = req("GET","/state")
    total_sent = sum(st["account_states"][s]["campaign"]["success"] for s in ["account3","account5","account7","account8","account10"])
    parts = []
    for slot in ["account3","account5","account7","account8","account10"]:
        c=st["account_states"][slot]["campaign"]
        parts.append(f"{slot}:{'run' if c['running'] else 'off'} c{c['cycle']} s{c['success']} {c['status'][:4]}")
    print(f"t+{(i+1)*10}s total_sent={total_sent}", " | ".join(parts))
    if total_sent > 0:
        break
    # check account3 logs for SEND
    logs=st["account_states"]["account3"].get("logs",[])
    sends=[L for L in logs if "SEND" in (L.get("event") or "")]
    if sends:
        print(" account3 send:", sends[-1].get("msg","")[:100])
'''
_, stdout, _ = c.exec_command(f"python3 - <<'PY'\n{remote}\nPY", timeout=200)
print(stdout.read().decode())
c.close()
