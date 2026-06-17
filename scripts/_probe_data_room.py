import os
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
import paramiko

PWD = os.environ.get("VPS_PASSWORD", "")
REMOTE = "/opt/telegramforward"
c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect("187.127.169.159", username="root", password=PWD, timeout=30)

cmds = [
    f"cd {REMOTE} && venv/bin/python -c \"from features.data_room_credentials_store import get_credentials; c=get_credentials(); print('handlers', len(c.get('handlers',[])), 'vault', len(c.get('service_accounts',[])), len(c.get('offer_letters',[])))\"",
    "curl -s -o /dev/null -w 'creds:%{http_code} %{content_type}\\n' http://127.0.0.1:8000/data-room/credentials",
    "curl -s http://127.0.0.1:8000/data-room/credentials | head -c 300",
    "curl -s -o /dev/null -w 'list:%{http_code} %{content_type}\\n' http://127.0.0.1:8000/data-room",
    "curl -s http://127.0.0.1:8000/data-room | head -c 300",
    "grep -n 'data-room/credentials' /opt/telegramforward/server.py | head -3",
    f"cd {REMOTE} && venv/bin/python -c \"from features import data_room_store; print(data_room_store.stats_summary())\"",
]
for cmd in cmds:
    print(">>>", cmd[:100])
    _, o, e = c.exec_command(cmd, timeout=60)
    out = o.read().decode("utf-8", "replace")
    err = e.read().decode("utf-8", "replace")
    if out:
        print(out[:800])
    if err:
        print("ERR:", err[:300])
c.close()
