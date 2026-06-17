import os
import paramiko

PWD = os.environ.get("VPS_PASSWORD", "")
c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect("187.127.169.159", username="root", password=PWD, timeout=30)
cmds = [
    "grep -rn 'voice/analytics' /opt/telegramforward.old/server.py /opt/telegramforward.old/core/ /opt/telegramforward.old/services/ 2>/dev/null",
    'curl -s "http://127.0.0.1:8000/openapi.json" | python3 -c "import sys,json; d=json.load(sys.stdin); print([p for p in sorted(d.get(\\\"paths\\\",{})) if \\\"voice\\\" in p])"',
]
for cmd in cmds:
    print(">>>", cmd[:100])
    _, o, _ = c.exec_command(cmd, timeout=90)
    print(o.read().decode("utf-8", errors="replace")[:1500])
c.close()
