#!/usr/bin/env python3
import socket, paramiko, sys, time
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
PASSWORD = "REMOVED_VPS_PASSWORD"
sock = socket.create_connection(("187.127.169.159", 22), timeout=30)
c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(hostname="187.127.169.159", username="root", password=PASSWORD, sock=sock)

patch_script = r'''
import pathlib
p = pathlib.Path("/opt/telegramforward.old/workers/account_worker.py")
src = p.read_text(encoding="utf-8")
marker = "CYCLE_DEBUG_PATCH_v1"
if marker in src:
    print("already patched")
else:
    old = """            except Exception as e:

                await self._log(f"Unexpected error (recovered): {e}", "error", action="cycle_error")

                apply_delay = False"""
    new = old.replace(
        'await self._log(f"Unexpected error (recovered): {e}", "error", action="cycle_error")',
        f'await self._log(f"Unexpected error (recovered): {{e}}", "error", action="cycle_error")\n                import traceback\n                pathlib.Path("/tmp/cycle_debug.log").open("a").write(f"{{marker}} CAMPAIGN {{self.slot}}: {{e}}\\n{{traceback.format_exc()}}\\n")'.replace("{marker}", marker)
    )
    if old not in src:
        print("NEEDLE NOT FOUND")
    else:
        src = src.replace(old, new)
        # also patch missing except in _execute_cycle - fix the dead code bug
        dead = """            return self._cycle_end_reason in ("complete", "cycle_wall_limit")

            await self._log(f"Cycle error (recovered): {e}", "error", action="cycle_error")"""
        fixed = """            return self._cycle_end_reason in ("complete", "cycle_wall_limit")

        except Exception as e:
            await self._log(f"Cycle error (recovered): {e}", "error", action="cycle_error")
            pathlib.Path("/tmp/cycle_debug.log").open("a").write(f"CYCLE_EXEC {self.slot}: {e}\\n{traceback.format_exc()}\\n")"""
        if dead in src and "except Exception as e:" not in src[src.find(dead)-200:src.find(dead)+50]:
            src = src.replace(dead, fixed)
            # add import traceback at top of except - need import in function
            src = src.replace(
                "        except Exception as e:\n            await self._log(f\"Cycle error (recovered): {e}\"",
                "        except Exception as e:\n            import traceback\n            await self._log(f\"Cycle error (recovered): {e}\""
            )
            print("fixed missing except block")
        p.write_text(src, encoding="utf-8")
        print("PATCHED OK")
'''

_, stdout, stderr = c.exec_command(f"python3 - <<'PY'\n{patch_script}\nPY", timeout=30)
print(stdout.read().decode())
print(stderr.read().decode())

# clear debug log, restart, start account7
cmds = [
    "rm -f /tmp/cycle_debug.log",
    "pm2 restart telegram-backend --update-env 2>&1 | tail -2",
]
for cmd in cmds:
    c.exec_command(cmd, timeout=60)

time.sleep(8)

start = r'''
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
print("started")
time.sleep(45)
'''
_, stdout, _ = c.exec_command(f"python3 - <<'PY'\n{start}\nPY", timeout=90)
print(stdout.read().decode())

_, stdout, _ = c.exec_command("cat /tmp/cycle_debug.log 2>/dev/null || echo NO DEBUG LOG", timeout=30)
print("\n=== DEBUG LOG ===")
print(stdout.read().decode(errors="replace")[:8000])

c.close()
