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

def req(method, path, data=None):
    r = urllib.request.Request("http://127.0.0.1:8000"+path, method=method)
    r.add_header("Content-Type", "application/json")
    if data is not None:
        r.data = json.dumps(data).encode()
    with opener.open(r, timeout=30) as resp:
        return json.loads(resp.read())

req("POST", "/auth/login", {"username":"admin","password":"734720077743"})

# stop all then start account7 campaign only
for i in range(1,11):
    try: req("POST", f"/account/account{i}/stop")
    except: pass
time.sleep(2)
req("POST", "/account/account7/start?feature=campaign")
print("Started account7 campaign")

for i in range(12):
    time.sleep(5)
    st = req("GET", "/state")
    a7 = st["account_states"]["account7"]
    camp = a7.get("campaign", {})
    print(f"t+{(i+1)*5}s status={camp.get('status')} notif={camp.get('notification','')[:80]} cycle={camp.get('cycle')} success={camp.get('success')} my_groups={camp.get('my_groups')}")
    logs = a7.get("logs", [])[-5:]
    for L in logs:
        m = L.get("message") or L.get("text") or ""
        if m: print("  log:", m[:150])
    if camp.get("success",0) > 0:
        break
'''

_, stdout, stderr = c.exec_command(f"python3 - <<'PY'\n{remote}\nPY", timeout=120)
print(stdout.read().decode(errors="replace"))
err = stderr.read().decode(errors="replace")
if err.strip(): print("STDERR:", err[:3000])
c.close()
