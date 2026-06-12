#!/usr/bin/env python3
import socket, paramiko, sys, time
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
PASSWORD = "8897870998s@SS"
sock = socket.create_connection(("187.127.169.159", 22), timeout=30)
c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(hostname="187.127.169.159", username="root", password=PASSWORD, sock=sock)
patch = r'''
import pathlib, re, py_compile
p = pathlib.Path("/opt/telegramforward.old/workers/account_worker.py")
src = p.read_text(encoding="utf-8")
if "ERRLOG2" not in src:
    src = src.replace(
        'await self._log(f"Cycle error (recovered): {e}", "error", action="cycle_error")',
        'await self._log(f"Cycle error (recovered): {e}", "error", action="cycle_error")\n            try:\n                import traceback\n                with open("/tmp/cycle_err2.log","a") as _f: _f.write(f"ERRLOG2 EXEC {self.slot}: {e!r}\\n{traceback.format_exc()}\\n")\n            except Exception: pass'
    )
    p.write_text(src, encoding="utf-8")
py_compile.compile(str(p), doraise=True)
print("ok")
'''
c.exec_command(f"python3 - <<'PY'\n{patch}\nPY", timeout=30)
c.exec_command("rm -f /tmp/cycle_err2.log; pm2 restart telegram-backend --update-env", timeout=60)
time.sleep(10)
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
req("POST","/account/account3/start?feature=campaign")
time.sleep(40)
'''
c.exec_command(f"python3 - <<'PY'\n{start}\nPY", timeout=60)
time.sleep(40)
_, stdout, _ = c.exec_command("cat /tmp/cycle_err2.log 2>/dev/null | tail -30", timeout=30)
print(stdout.read().decode() or "empty")
# account3 logs
cmd = r'''curl -s -c /tmp/cj -b /tmp/cj -X POST http://127.0.0.1:8000/auth/login -H 'Content-Type: application/json' -d '{"username":"admin","password":"734720077743"}' > /dev/null; curl -s -b /tmp/cj http://127.0.0.1:8000/state | python3 -c "
import json,sys
d=json.load(sys.stdin)
for L in d['account_states']['account3'].get('logs',[])[-15:]:
    print(L.get('event'), L.get('msg','')[:140])
"'''
_, stdout, _ = c.exec_command(cmd, timeout=30)
print("\nlogs:", stdout.read().decode())
c.close()
