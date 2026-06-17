#!/usr/bin/env python3
import json, socket, paramiko, sys, time
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
PASSWORD = "8897870998s@SS"
sock = socket.create_connection(("187.127.169.159", 22), timeout=30)
c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(hostname="187.127.169.159", username="root", password=PASSWORD, sock=sock)

remote = r'''
import json, urllib.request, http.cookiejar, time
cj = http.cookiejar.CookieJar()
opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))
def req(m,p,d=None):
    r=urllib.request.Request("http://127.0.0.1:8000"+p,method=m)
    r.add_header("Content-Type","application/json")
    if d: r.data=json.dumps(d).encode()
    with opener.open(r,timeout=30) as resp: return json.loads(resp.read())
req("POST","/auth/login",{"username":"admin","password":"734720077743"})
for i in range(1,11):
    try: req("POST",f"/account/account{i}/stop")
    except: pass
time.sleep(2)
req("POST","/account/account7/start?feature=campaign")
print("started account7")
for i in range(18):
    time.sleep(5)
    st = req("GET","/state")
    a7 = st["account_states"]["account7"]
    camp = a7["campaign"]
    events = [L.get("event") for L in a7.get("logs",[])[-3:]]
    msgs = [L.get("msg","") for L in a7.get("logs",[])[-3:]]
    print(f"t+{(i+1)*5}s status={camp.get('status')} cycle={camp.get('cycle')} sent={camp.get('success')} events={events}")
    for m in msgs:
        if "CYCLE_START" in m or "cycle_error" in m or "Cycle error" in m or "SEND" in m or "GROUP_SOURCE" in m:
            print(" ", m)
    if camp.get("success",0) > 0 or camp.get("cycle",0) > 0:
        print("PROGRESS!")
        break
'''

_, stdout, stderr = c.exec_command(f"python3 - <<'PY'\n{remote}\nPY", timeout=120)
print(stdout.read().decode())
print(stderr.read().decode()[:2000])

_, stdout, _ = c.exec_command("grep 'account7' /root/.pm2/logs/telegram-backend-error.log | tail -15", timeout=30)
print("\n=== recent account7 errors ===")
print(stdout.read().decode(errors="replace"))
c.close()
