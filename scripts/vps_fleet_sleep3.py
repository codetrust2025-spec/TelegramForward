#!/usr/bin/env python3
import socket, paramiko, sys
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
PASSWORD = "REMOVED_VPS_PASSWORD"
sock = socket.create_connection(("187.127.169.159", 22), timeout=30)
c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(hostname="187.127.169.159", username="root", password=PASSWORD, sock=sock)

cmds = [
    "grep -n 'FORWARD_REST\\|pick_forward_rest\\|minCountdown\\|sleeping' /opt/telegramforward.old/core/posting_mode.py /opt/telegramforward.old/core/worker_registry.py /opt/telegramforward.old/core/*.py 2>/dev/null | head -40",
    "grep -rn 'minCountdown' /opt/telegramforward.old/core 2>/dev/null",
    """cd /opt/telegramforward.old && PYTHONPATH=. ./venv/bin/python -c "
from core.worker_registry import manager
s = manager.build_ui_state()
f = s.get('fleet') or {}
print('minCountdown', f.get('minCountdown'))
print('sleepingCount', f.get('sleepingCount'))
print('runningCount', f.get('runningCount'))
for slot, st in sorted((s.get('account_states') or {}).items()):
    if st.get('forwarding_running') or st.get('status') == 'sleeping':
        print(slot, 'status', st.get('status'), 'next_cycle_in', st.get('next_cycle_in'), 'fwd', st.get('forwarding_running'))
"
""",
]
for cmd in cmds:
    print("===", cmd[:80], "===")
    _, stdout, stderr = c.exec_command(cmd, timeout=90)
    out = stdout.read().decode("utf-8", errors="replace")
    err = stderr.read().decode("utf-8", errors="replace")
    print(out or err)
c.close()
