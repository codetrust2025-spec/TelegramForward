#!/usr/bin/env python3
"""Reset account health scores and verify campaign posting."""
import json, socket, paramiko, sys, time
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
PASSWORD = "REMOVED_VPS_PASSWORD"
sock = socket.create_connection(("187.127.169.159", 22), timeout=30)
c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(hostname="187.127.169.159", username="root", password=PASSWORD, sock=sock)

reset = r'''
import json, os, pathlib
for slot in ["account3","account5","account7","account8","account10"]:
    p = pathlib.Path(f"/opt/telegramforward.old/data/accounts/{slot}/group_intelligence.json")
    if not p.exists():
        continue
    data = json.loads(p.read_text())
    acct = data.setdefault("account", {})
    acct["health_score"] = 100.0
    acct["delay_multiplier"] = 1.0
    acct["cycles_without_flood"] = 10
    p.write_text(json.dumps(data, indent=2))
    cp = pathlib.Path(f"/opt/telegramforward.old/data/accounts/{slot}/cycle_checkpoint.json")
    if cp.exists(): cp.unlink()
    print("reset", slot, "health=100")
'''
_, stdout, _ = c.exec_command(f"python3 - <<'PY'\n{reset}\nPY", timeout=30)
print(stdout.read().decode())

c.exec_command("pm2 restart telegram-backend --update-env", timeout=60)
time.sleep(12)

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
for slot in ["account3","account5","account7","account8","account10"]:
    req("POST", f"/account/{slot}/start?feature=campaign")
    time.sleep(1)
for slot in ["account1","account2","account4","account6","account9"]:
    req("POST", f"/account/{slot}/start?feature=forwarding")
    time.sleep(1)
print("fleet started")
for i in range(30):
    time.sleep(10)
    st = req("GET","/state")
    total = sum(st["account_states"][s]["campaign"]["success"] for s in ["account3","account5","account7","account8","account10"])
    fail = sum(st["account_states"][s]["campaign"]["failed"] for s in ["account3","account5","account7","account8","account10"])
    h = st["account_states"]["account10"].get("health_score")
    c10 = st["account_states"]["account10"]["campaign"]
    print(f"t+{(i+1)*10}s sent={total} fail={fail} a10_health={h} a10_cycle={c10['cycle']} a10_sent={c10['success']}")
    if total > 0:
        for s in ["account3","account5","account7","account8","account10"]:
            cc = st["account_states"][s]["campaign"]
            if cc["success"] or cc["failed"]:
                print(f"  {s}: ok={cc['success']} fail={cc['failed']}")
        break
'''
_, stdout, _ = c.exec_command(f"python3 - <<'PY'\n{test}\nPY", timeout=330)
print(stdout.read().decode())
c.close()
