#!/usr/bin/env python3
import socket, paramiko, sys, time
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
PASSWORD = "REMOVED_VPS_PASSWORD"
sock = socket.create_connection(("187.127.169.159", 22), timeout=30)
c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(hostname="187.127.169.159", username="root", password=PASSWORD, sock=sock)

patch = r'''
import pathlib
p = pathlib.Path("/opt/telegramforward.old/workers/account_worker.py")
src = p.read_text(encoding="utf-8")
needle = 'await self._log(f"Cycle error (recovered): {e}", "error", action="cycle_error")'
if "CYCLE_ERR_FILE" not in src:
    src = src.replace(
        needle,
        needle + '\n            try:\n                import traceback\n                with open("/tmp/cycle_err.log", "a") as _f:\n                    _f.write(f"CYCLE_ERR_FILE {self.slot}: {e!r}\\n{traceback.format_exc()}\\n")\n            except Exception:\n                pass'
    )
    src = src.replace(
        'await self._log(f"Unexpected error (recovered): {e}", "error", action="cycle_error")',
        'await self._log(f"Unexpected error (recovered): {e}", "error", action="cycle_error")\n                try:\n                    import traceback\n                    with open("/tmp/cycle_err.log", "a") as _f:\n                        _f.write(f"OUTER_ERR {self.slot}: {e!r}\\n{traceback.format_exc()}\\n")\n                except Exception:\n                    pass'
    )
    p.write_text(src, encoding="utf-8")
    print("patched file logging")
else:
    print("already patched")
import py_compile
py_compile.compile(str(p), doraise=True)
print("ok")
'''
_, stdout, _ = c.exec_command(f"python3 - <<'PY'\n{patch}\nPY", timeout=30)
print(stdout.read().decode())

c.exec_command("rm -f /tmp/cycle_err.log; pm2 restart telegram-backend --update-env", timeout=60)
time.sleep(8)

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
for i in range(1,11):
    try: req("POST",f"/account/account{i}/stop")
    except: pass
time.sleep(2)
req("POST","/account/account7/start?feature=campaign")
time.sleep(35)
'''
c.exec_command(f"python3 - <<'PY'\n{start}\nPY", timeout=60)
time.sleep(35)
_, stdout, _ = c.exec_command("cat /tmp/cycle_err.log 2>/dev/null || echo EMPTY", timeout=30)
print("\n=== ERR LOG ===")
print(stdout.read().decode(errors="replace")[:10000])
c.close()
