#!/usr/bin/env python3
import socket, paramiko, sys
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
PASSWORD = "REMOVED_VPS_PASSWORD"
sock = socket.create_connection(("187.127.169.159", 22), timeout=30)
c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(hostname="187.127.169.159", username="root", password=PASSWORD, sock=sock)

# Patch temporary debug logging into campaign loop except block
patch = r'''
import pathlib
p = pathlib.Path("/opt/telegramforward.old/workers/account_worker.py")
src = p.read_text(encoding="utf-8")
needle = 'await self._log(f"Unexpected error (recovered): {e}", "error", action="cycle_error")'
if needle in src and "CYCLE_DEBUG_FILE" not in src:
    repl = needle + '\n                import traceback\n                pathlib.Path("/tmp/cycle_debug.log").open("a").write(f"\\n{self.slot}: {e}\\n{traceback.format_exc()}\\n")'
    p.write_text(src.replace(needle, repl), encoding="utf-8")
    print("PATCHED")
else:
    print("ALREADY PATCHED OR NEEDLE MISSING", needle in src)
'''
_, stdout, _ = c.exec_command(f"python3 - <<'PY'\n{patch}\nPY", timeout=30)
print(stdout.read().decode())

# Also patch _execute_cycle early returns - add debug at start
patch2 = r'''
import pathlib
p = pathlib.Path("/opt/telegramforward.old/workers/account_worker.py")
src = p.read_text(encoding="utf-8")
needle = 'async def _execute_cycle(self) -> bool:'
if 'cycle_exec_debug' not in src:
    src = src.replace(needle, needle + '\n        import pathlib as _pl\n        _dbg = lambda m: _pl.Path("/tmp/cycle_exec_debug.log").open("a").write(f"{self.slot}: {m}\\n")')
    # patch return False after health - find Connection failed
    src = src.replace(
        'f"Connection failed — retry in {recovery_wait}s",',
        'f"Connection failed — retry in {recovery_wait}s",\n                        )\n                        _dbg("connection_failed")',
        1
    )
    print("partial patch skipped - manual")
p.write_text(src, encoding="utf-8") if 'cycle_exec_debug' not in p.read_text() else None
'''
# restart pm2 and trigger cycle
_, stdout, _ = c.exec_command("pm2 restart telegram-backend --update-env 2>&1 | tail -3", timeout=60)
print(stdout.read().decode())
time.sleep = None
c.close()
