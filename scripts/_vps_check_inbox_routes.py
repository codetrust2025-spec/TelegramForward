import os
import paramiko

PWD = os.environ.get("VPS_PASSWORD", "")
REMOTE = "/opt/telegramforward.old"
c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect("187.127.169.159", username="root", password=PWD, timeout=30)
cmds = [
    f"grep -n '@app.*alerts\\|/push\\|vapid' {REMOTE}/server.py | head -30",
    f"grep -rn 'vapid\\|/alerts' {REMOTE}/core {REMOTE}/features 2>/dev/null | head -25",
    "curl -s -o /dev/null -w '%{http_code} %{content_type}' http://127.0.0.1:8000/alerts",
    "curl -s http://127.0.0.1:8000/alerts | head -c 120",
    "curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1:8000/push/vapid-public-key",
    "curl -s http://127.0.0.1:8000/push/vapid-public-key | head -c 120",
    "curl -s -o /dev/null -w '%{http_code}' 'http://127.0.0.1:8000/inbox?sync=0'",
]
for cmd in cmds:
    print("===", cmd[:95])
    _, o, _ = c.exec_command(cmd, timeout=60)
    print(o.read().decode("utf-8", errors="replace")[:800])
c.close()
