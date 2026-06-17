#!/usr/bin/env python3
import socket, paramiko, sys
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
PASSWORD = "REMOVED_VPS_PASSWORD"
sock = socket.create_connection(("187.127.169.159", 22), timeout=30)
c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(hostname="187.127.169.159", username="root", password=PASSWORD, sock=sock)

cmds = [
    "sed -n '71,98p' /opt/telegramforward.old/services/account_manager.py",
    "sed -n '2420,2460p' /opt/telegramforward.old/workers/account_worker.py",
    "grep FORWARD_REST /opt/telegramforward.old/.env 2>/dev/null || echo '(defaults 600-1800)'",
]
for cmd in cmds:
    print("===", cmd)
    _, stdout, _ = c.exec_command(cmd, timeout=60)
    print(stdout.read().decode("utf-8", errors="replace"))

script = '''
from services.account_manager import account_manager
state = account_manager.build_ui_state()
fwd = ["account1","account2","account4","account6","account9"]
st = state.get("account_states") or {}
status = state.get("account_status") or {}
print("LIVE:")
mins = []
for slot in fwd:
    a = st.get(slot) or {}
    lc = (status.get(slot) or {}).get("lifecycle")
    n = int(a.get("next_cycle_in") or 0)
    print(f"  {slot}: lifecycle={lc} next_cycle_in={n}s ({n//60}m {n%60:02d}s) running={a.get('running')} fwd={a.get('forwarding_running')}")
    if n > 0: mins.append((n, slot))
if mins:
    m = min(mins)
    print(f"=> Dashboard 'Fleet sleeping' ~ {m[0]//60}m {m[0]%60:02d}s (min across fleet)")
else:
    print("=> No rest timer active right now")
'''
_, stdout, stderr = c.exec_command(
    f"cd /opt/telegramforward.old && set -a && . ./.env && set +a && PYTHONPATH=. ./venv/bin/python - <<'PY'\n{script}\nPY",
    timeout=90,
)
print("=== LIVE STATE ===")
print(stdout.read().decode("utf-8", errors="replace"))
err = stderr.read().decode("utf-8", errors="replace")
if err.strip(): print("ERR:", err[-1500:])
c.close()
