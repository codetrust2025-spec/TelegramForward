#!/usr/bin/env python3
import socket, paramiko, sys, time
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
PASSWORD = "REMOVED_VPS_PASSWORD"
sock = socket.create_connection(("187.127.169.159", 22), timeout=30)
c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(hostname="187.127.169.159", username="root", password=PASSWORD, sock=sock)

reset = r'''
import json, pathlib
# reset health in group_intelligence if present
for slot in ["account3","account5","account7","account8","account10"]:
    p = pathlib.Path(f"/opt/telegramforward.old/data/accounts/{slot}/group_intelligence.json")
    if p.exists():
        data = json.loads(p.read_text())
        if "account_health" in data:
            data["account_health"] = {"score": 100, "delay_multiplier": 1.0}
        if "health" in data:
            data["health"] = {"score": 100}
        p.write_text(json.dumps(data, indent=2))
        print("reset intel", slot)
print("done")
'''
_, stdout, _ = c.exec_command(f"python3 - <<'PY'\n{reset}\nPY", timeout=30)
print(stdout.read().decode())

# restart account10 only
start = r'''
import json, urllib.request, http.cookiejar, time, os
cj = http.cookiejar.CookieJar()
op = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))
def req(m,p,d=None):
    r=urllib.request.Request("http://127.0.0.1:8000"+p,method=m)
    r.add_header("Content-Type","application/json")
    if d: r.data=json.dumps(d).encode()
    with op.open(r,timeout=30) as resp: return json.loads(resp.read())
req("POST","/auth/login",{"username":"admin","password":"734720077743"})
req("POST","/account/account10/stop")
time.sleep(2)
os.remove("/opt/telegramforward.old/data/accounts/account10/cycle_checkpoint.json") if os.path.exists("/opt/telegramforward.old/data/accounts/account10/cycle_checkpoint.json") else None
req("POST","/account/account10/start?feature=campaign")
for i in range(18):
    time.sleep(10)
    st = req("GET","/state")
    a10 = st["account_states"]["account10"]
    camp = a10["campaign"]
    health = a10.get("health_score")
    sends = [L for L in a10.get("logs",[]) if "SEND" in (L.get("event") or "")]
    sched = [L for L in a10.get("logs",[]) if "skip" in (L.get("msg") or "").lower() and "Scheduler" in (L.get("msg") or "")]
    print(f"t+{(i+1)*10}s cycle={camp.get('cycle')} sent={camp.get('success')} fail={camp.get('failed')} health={health} sends={len(sends)} sched={len(sched)}")
    if camp.get("success",0) > 0:
        print("SUCCESS")
        break
    if sends:
        print(sends[-1].get("msg","")[:120])
'''
_, stdout, _ = c.exec_command(f"python3 - <<'PY'\n{start}\nPY", timeout=200)
print(stdout.read().decode())
c.close()
