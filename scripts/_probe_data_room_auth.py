import json
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
    f"cd {REMOTE} && venv/bin/python -c \"import json; d=json.load(open('data/data_room/credentials.json')); print('admin_pwd_len', len(d['admin']['password']))\"",
    f"""curl -s -c /tmp/ta.cookie -X POST http://127.0.0.1:8000/auth/login -H 'Content-Type: application/json' -d '{{"username":"admin","password":"734720077743"}}'""",
    "curl -s -b /tmp/ta.cookie -o /dev/null -w 'creds:%{http_code} time:%{time_total}\\n' http://127.0.0.1:8000/data-room/credentials",
    "curl -s -b /tmp/ta.cookie http://127.0.0.1:8000/data-room/credentials | head -c 250",
    "curl -s -b /tmp/ta.cookie -o /dev/null -w 'list:%{http_code} time:%{time_total}\\n' http://127.0.0.1:8000/data-room",
    "curl -s -b /tmp/ta.cookie http://127.0.0.1:8000/data-room | head -c 200",
]
for cmd in cmds:
    print(">>>", cmd[:90])
    _, o, e = c.exec_command(cmd, timeout=30)
    out = o.read().decode("utf-8", "replace")
    err = e.read().decode("utf-8", "replace")
    if out:
        print(out[:600])
    if err:
        print("ERR:", err[:200])
c.close()
