import os
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
import paramiko

PWD = os.environ.get("VPS_PASSWORD", "")
c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect("187.127.169.159", username="root", password=PWD, timeout=30)
cmds = [
    'grep -r "Offer letters" /opt/telegramforward --include="*.py" --include="*.jsx" --include="*.js" --include="*.json" 2>/dev/null | head -30',
    'grep -r "offer_letter" /opt/telegramforward --include="*.py" --include="*.jsx" --include="*.js" 2>/dev/null | head -30',
    'grep -r "Drive folder" /opt/telegramforward --include="*.py" --include="*.jsx" --include="*.js" 2>/dev/null | head -30',
    'find /opt/telegramforward/data -iname "*offer*" 2>/dev/null | head -20',
    'ls -la /opt/telegramforward/data/ 2>/dev/null',
]
for cmd in cmds:
    print(">>>", cmd)
    _, o, _ = c.exec_command(cmd)
    print(o.read().decode("utf-8", "replace"))
c.close()
