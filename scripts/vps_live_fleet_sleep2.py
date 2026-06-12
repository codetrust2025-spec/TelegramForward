#!/usr/bin/env python3
import socket, paramiko, sys
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
PASSWORD = "REMOVED_VPS_PASSWORD"
sock = socket.create_connection(("187.127.169.159", 22), timeout=30)
c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(hostname="187.127.169.159", username="root", password=PASSWORD, sock=sock)

script = '''
import json
from pathlib import Path
from services.account_manager import AccountManager
am = AccountManager()
state = am.get_dashboard_state()
fwd = ["account1","account2","account4","account6","account9"]
st = state.get("account_states") or {}
print("LIVE forwarding rest timers:")
mins = []
for slot in fwd:
    a = st.get(slot) or {}
    n = int(a.get("next_cycle_in") or 0)
    fwd_n = int(a.get("forwarding_next_cycle_in") or (a.get("forwarding") or {}).get("next_cycle_in") or 0)
    status = a.get("status")
    print(f"  {slot}: status={status} running={a.get('running')} forwarding_running={a.get('forwarding_running')} next_cycle_in={n}s ({n//60}m{n%60:02d}s) fwd_next={fwd_n}")
    if n > 0: mins.append((n, slot))
if mins:
    m = min(mins)
    print(f"FLEET SLEEPING shows: {m[0]//60}m {m[0]%60:02d}s (shortest on {m[1]})")
'''
_, stdout, stderr = c.exec_command(
    f"cd /opt/telegramforward.old && set -a && . ./.env && set +a && PYTHONPATH=. ./venv/bin/python - <<'PY'\n{script}\nPY",
    timeout=90,
)
print(stdout.read().decode("utf-8", errors="replace"))
err = stderr.read().decode("utf-8", errors="replace")
if err.strip(): print("ERR:", err[-2000:])
c.close()
