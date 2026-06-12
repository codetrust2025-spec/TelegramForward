#!/usr/bin/env python3
import socket, paramiko, sys, time
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
PASSWORD = "REMOVED_VPS_PASSWORD"
sock = socket.create_connection(("187.127.169.159", 22), timeout=30)
c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(hostname="187.127.169.159", username="root", password=PASSWORD, sock=sock)

fix = r'''
import pathlib, shutil
p = pathlib.Path("/opt/telegramforward.old/workers/account_worker.py")
src = p.read_text(encoding="utf-8")

# Remove bad debug patches
bad1 = "                import traceback\n                pathlib.Path(\"/tmp/cycle_debug.log\").open(\"a\").write(f\"CYCLE_DEBUG_PATCH_v1 CAMPAIGN {self.slot}: {e}\\n{traceback.format_exc()}\\n\")"
if bad1 in src:
    src = src.replace("\n" + bad1, "")
    print("removed bad campaign patch")

# Ensure proper except block exists (fix pre-existing bug)
dead = """            return self._cycle_end_reason in ("complete", "cycle_wall_limit")

            await self._log(f"Cycle error (recovered): {e}", "error", action="cycle_error")"""

fixed = """            return self._cycle_end_reason in ("complete", "cycle_wall_limit")

        except Exception as e:
            await self._log(f"Cycle error (recovered): {e}", "error", action="cycle_error")"""

if "        except Exception as e:\n            import traceback\n            await self._log(f\"Cycle error (recovered): {e}\"" in src:
    # already has except from our patch, just remove pathlib line if any
    src = src.replace("\n            pathlib.Path(\"/tmp/cycle_debug.log\").open(\"a\").write(f\"CYCLE_EXEC {self.slot}: {e}\\n{traceback.format_exc()}\\n\")", "")
    src = src.replace("\n            import traceback", "", 1)  # only first in except
    print("cleaned except block")
elif dead in src:
    src = src.replace(dead, fixed)
    print("added except block")
else:
    print("except block state unknown - checking...")
    if "except Exception as e:" in src and "Cycle error (recovered)" in src:
        print("except already present")
    else:
        print("MANUAL FIX NEEDED")

p.write_text(src, encoding="utf-8")
# verify compile
import py_compile
try:
    py_compile.compile(str(p), doraise=True)
    print("SYNTAX OK")
except py_compile.PyCompileError as e:
    print("SYNTAX FAIL", e)
    # restore from backup
    bak = pathlib.Path("/opt/telegramforward.old/_ai_deploy_backup_20260525_234049/workers/account_worker.py")
    if bak.exists():
        shutil.copy(bak, p)
        print("RESTORED FROM BACKUP")
'''

_, stdout, stderr = c.exec_command(f"python3 - <<'PY'\n{fix}\nPY", timeout=30)
print(stdout.read().decode())
print(stderr.read().decode())

# read _filter_groups
_, stdout, _ = c.exec_command("sed -n '640,700p' /opt/telegramforward.old/workers/account_worker.py", timeout=30)
print("\n=== _filter_groups ===")
print(stdout.read().decode(errors="replace"))

# grep NO_GROUPS_RETRY
_, stdout, _ = c.exec_command("grep -n 'NO_GROUPS_RETRY' /opt/telegramforward.old/workers/account_worker.py /opt/telegramforward.old/core/*.py 2>/dev/null | head -5", timeout=30)
print("\n=== NO_GROUPS ===")
print(stdout.read().decode())

c.exec_command("pm2 restart telegram-backend --update-env", timeout=60)
time.sleep(10)
c.close()
print("restarted")
