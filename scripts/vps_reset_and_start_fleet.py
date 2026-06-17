#!/usr/bin/env python3
import json, socket, paramiko, sys, time
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
PASSWORD = "REMOVED_VPS_PASSWORD"
sock = socket.create_connection(("187.127.169.159", 22), timeout=30)
c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(hostname="187.127.169.159", username="root", password=PASSWORD, sock=sock)

# reset checkpoint for account7
c.exec_command("rm -f /opt/telegramforward.old/data/accounts/account7/cycle_checkpoint.json", timeout=10)

test = r'''
import json, urllib.request, http.cookiejar, time
cj = http.cookiejar.CookieJar()
op = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))
def req(m,p,d=None):
    r=urllib.request.Request("http://127.0.0.1:8000"+p,method=m)
    r.add_header("Content-Type","application/json")
    if d: r.data=json.dumps(d).encode()
    with op.open(r,timeout=30) as resp: return json.loads(resp.read())
req("POST","/auth/login",{"username":"admin","password":"734720077743"})
req("POST","/account/account7/stop")
time.sleep(2)
req("POST","/account/account7/start?feature=campaign")
print("restarted account7 fresh")
for i in range(24):
    time.sleep(10)
    st = req("GET","/state")
    a7 = st["account_states"]["account7"]
    camp = a7["campaign"]
    logs = a7.get("logs",[])
    sends = [L for L in logs if L.get("event") in ("SEND_OK","SEND_FAIL","SEND_SUCCESS") or "SEND" in (L.get("event") or "")]
    skips = [L for L in logs[-10:] if "skip" in (L.get("action") or "").lower() or "SKIP" in (L.get("event") or "")]
    print(f"t+{(i+1)*10}s cycle={camp.get('cycle')} sent={camp.get('success')} fail={camp.get('failed')} cur={a7.get('current_group','')[:35]}")
    if sends:
        print(" SEND:", sends[-1].get("event"), sends[-1].get("msg","")[:120])
    if camp.get("success",0) >= 1:
        print("SUCCESS")
        break
    if skips and i > 2:
        print(" skip sample:", skips[-1].get("msg","")[:100])
'''
_, stdout, _ = c.exec_command(f"python3 - <<'PY'\n{test}\nPY", timeout=280)
print(stdout.read().decode())

# start all campaign + forwarding
start_all = r'''
import json, urllib.request, http.cookiejar, time
cj = http.cookiejar.CookieJar()
op = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))
def req(m,p,d=None):
    r=urllib.request.Request("http://127.0.0.1:8000"+p,method=m)
    r.add_header("Content-Type","application/json")
    if d: r.data=json.dumps(d).encode()
    with op.open(r,timeout=30) as resp: return json.loads(resp.read())
req("POST","/auth/login",{"username":"admin","password":"734720077743"})
for slot in ["account3","account5","account8","account10"]:
    req("POST", f"/account/{slot}/start?feature=campaign")
    time.sleep(1)
for slot in ["account1","account2","account4","account6","account9"]:
    req("POST", f"/account/{slot}/start?feature=forwarding")
    time.sleep(1)
print("all accounts started")
st = req("GET","/state")
for slot in st["account_slots"]:
    a = st["account_states"][slot]
    print(slot, "camp", a["campaign"]["running"], a["campaign"]["status"], "fwd", a["forwarding"]["running"])
'''
_, stdout, _ = c.exec_command(f"python3 - <<'PY'\n{start_all}\nPY", timeout=60)
print("\n=== FLEET ===")
print(stdout.read().decode())
c.close()
