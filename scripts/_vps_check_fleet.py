import os
import sys

import paramiko

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect("187.127.169.159", username="root", password=os.environ.get("VPS_PASSWORD", ""), timeout=30)
cmds = [
    "grep -n '/fleet/' /opt/telegramforward/server.py | head -12",
    "test -f /opt/telegramforward/core/fleet_defaults.py && echo fleet_defaults:yes || echo fleet_defaults:no",
    "test -f /opt/telegramforward/services/fleet_setup_service.py && echo fleet_service:yes || echo fleet_service:no",
    "grep fleet /opt/telegramforward/core/dashboard_auth_vps.py",
    "curl -s -w '\\nhttp:%{http_code}' http://127.0.0.1:8000/fleet/defaults | head -c 400",
]
for cmd in cmds:
    _, o, _ = c.exec_command(cmd, timeout=25)
    print(">>>", cmd)
    print(o.read().decode("utf-8", "replace"))
c.close()
