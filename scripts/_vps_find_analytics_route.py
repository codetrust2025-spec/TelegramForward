import os
import paramiko

PWD = os.environ.get("VPS_PASSWORD", "")
c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect("187.127.169.159", username="root", password=PWD, timeout=30)
cmds = [
    "pm2 describe telegram-backend 2>/dev/null | grep -E 'script path|exec cwd|PORT'",
    "grep -rn '@app\\.' /opt/telegramforward.old/server.py | grep -i analytics",
    "grep -rn '\"/analytics' /opt/telegramforward.old /opt/telegramforward 2>/dev/null | head -30",
    "grep -rn 'analytics_summary' /opt/telegramforward.old 2>/dev/null | head -15",
    "curl -s http://127.0.0.1:8000/openapi.json | head -c 200",
    'curl -s http://127.0.0.1:8000/openapi.json | python3 -c "import sys,json; d=json.load(sys.stdin); print([p for p in d.get(\\\"paths\\\",{}) if \\\"anal\\\" in p.lower()][:20])"',
]
for cmd in cmds:
    print(">>>", cmd[:100])
    _, o, e = c.exec_command(cmd, timeout=90)
    out = o.read().decode("utf-8", errors="replace")
    print(out[:1200] if out else "(empty)")
    err = e.read().decode("utf-8", errors="replace")
    if err.strip():
        print("ERR:", err[:400])
c.close()
