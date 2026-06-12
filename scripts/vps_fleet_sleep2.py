#!/usr/bin/env python3
import re, socket, paramiko, sys
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
PASSWORD = "8897870998s@SS"
sock = socket.create_connection(("187.127.169.159", 22), timeout=30)
c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(hostname="187.127.169.159", username="root", password=PASSWORD, sock=sock)
path = "/opt/telegramforward.old/static/assets/app-BkUk1ts9.js"
_, stdout, _ = c.exec_command(f"grep -o 'Fleet sleeping' {path} | wc -l", timeout=30)
print("count:", stdout.read().decode().strip())
_, stdout, _ = c.exec_command(f"python3 -c \"import re; s=open('{path}',encoding='utf-8',errors='ignore').read(); m=re.search(r'.{{0,80}}Fleet sleeping.{{0,120}}', s); print(m.group(0) if m else 'not found')\"", timeout=60)
print(stdout.read().decode())

# get live minCountdown from API would need auth - check worker state file
script = '''
import json
from core.worker_registry import manager
state = manager.build_ui_state()
fleet = state.get("fleet") or {}
print("fleet keys:", list(fleet.keys())[:20])
print("minCountdown:", fleet.get("minCountdown"))
print("sleepingCount:", fleet.get("sleepingCount"))
print("runningCount:", fleet.get("runningCount"))
for slot in [f"account{i}" for i in range(1,11)]:
    st = (state.get("account_states") or {}).get(slot) or {}
    if st.get("forwarding_running") or st.get("campaign_running"):
        print(slot, "fwd", st.get("forwarding_running"), "camp", st.get("campaign_running"),
              "next", st.get("next_cycle_in"), "status", st.get("status"))
'''
_, stdout, _ = c.exec_command(f"cd /opt/telegramforward.old && PYTHONPATH=. ./venv/bin/python - <<'PY'\n{script}\nPY", timeout=60)
print(stdout.read().decode())
c.close()
