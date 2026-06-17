import os
import paramiko

PWD = os.environ.get("VPS_PASSWORD", "")
c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect("187.127.169.159", username="root", password=PWD, timeout=30)
cmds = [
    "grep -rn 'voice/analytics' /opt/telegramforward.old 2>/dev/null | head -20",
    'curl -s "http://127.0.0.1:8000/voice/analytics?days=30" | head -c 120',
    'curl -s -o /dev/null -w "%{http_code} %{content_type}\\n" "http://127.0.0.1:8000/voice/analytics?days=30"',
    "grep -rn 'install.*voice' /opt/telegramforward.old/server.py | head -15",
]
for cmd in cmds:
    print(">>>", cmd)
    _, o, _ = c.exec_command(cmd, timeout=60)
    print(o.read().decode("utf-8", errors="replace")[:600])
c.close()
