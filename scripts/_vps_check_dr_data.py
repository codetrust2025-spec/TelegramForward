import os
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
import paramiko

PWD = os.environ.get("VPS_PASSWORD", "")
c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect("187.127.169.159", username="root", password=PWD, timeout=30)
cmds = [
    "test -f /opt/telegramforward/data/data_room/credentials.json && wc -c /opt/telegramforward/data/data_room/credentials.json || echo NO_CREDS",
    "test -f /opt/telegramforward/data/data_room/opportunities.json && wc -c /opt/telegramforward/data/data_room/opportunities.json || echo NO_OPP",
    "grep -c 'dr-vault' /opt/telegramforward/dashboard/src/index.css 2>/dev/null || echo 0",
    "grep -c 'dr-vault' /opt/telegramforward/static/assets/index-C4RxiluA.css 2>/dev/null || echo 0",
    "curl -s -o /dev/null -w '%{http_code}' -H 'Cookie: ' http://127.0.0.1:8000/data-room",
]
for cmd in cmds:
    print(">>>", cmd)
    _, o, _ = c.exec_command(cmd)
    print(o.read().decode())
c.close()
