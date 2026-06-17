import os
import re
import paramiko

PWD = os.environ.get("VPS_PASSWORD", "")
c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect("187.127.169.159", username="root", password=PWD, timeout=30)
_, o, _ = c.exec_command(
    r"""python3 <<'PY'
import re
for path in ['/opt/telegramforward/dashboard/src/teleautomation.css',
             '/opt/telegramforward/dashboard/src/index.css']:
    try:
        t = open(path, encoding='utf-8', errors='replace').read()
    except OSError:
        continue
    hits = []
    for m in re.finditer(r'[^@{}]{0,100}crm-inbox-toolbar[^@{}]{0,120}', t):
        s = m.group(0)
        if 'display' in s or 'column' in s or 'none' in s or 'flex-direction' in s:
            hits.append(s[:200])
    if hits:
        print('FILE', path)
        for h in hits:
            print(h)
            print('---')
PY""",
    timeout=60,
)
print(o.read().decode("utf-8", errors="replace"))
c.close()
