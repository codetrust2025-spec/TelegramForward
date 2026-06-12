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
for i in range(12):
    time.sleep(10)
    st = req("GET","/state")
    a7 = st["account_states"]["account7"]
    camp = a7["campaign"]
    sends = [L for L in a7.get("logs",[]) if "SEND" in (L.get("event") or "")]
    print(f"t+{(i+1)*10}s sent={camp.get('success')} fail={camp.get('failed')} cur={a7.get('current_group','')[:40]} send_events={len(sends)}")
    if sends:
        print(" last send:", sends[-1].get("event"), sends[-1].get("msg","")[:100])
    if camp.get("success",0) >= 1:
        break
'''
_, stdout, _ = c.exec_command(f"python3 - <<'PY'\n{remote}\nPY", timeout=150)
print(stdout.read().decode())
c.close()
