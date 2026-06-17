import os
import re
import paramiko

PWD = os.environ.get("VPS_PASSWORD", "")
c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect("187.127.169.159", username="root", password=PWD, timeout=30)
_, o, _ = c.exec_command(
    "grep -o 'crm-layout[^\"]*' /opt/telegramforward/dashboard/src/teleautomation-app.jsx | sort -u",
    timeout=60,
)
print(o.read().decode("utf-8", errors="replace"))

# desktop: min-width 769 might not hide toolbar
_, o, _ = c.exec_command(
    r"""python3 -c "
import re
t=open('/opt/telegramforward/dashboard/src/teleautomation.css','r',errors='replace').read()
if not t.strip():
    t=open('/opt/telegramforward/dashboard/src/index.css').read()
# rules that show toolbar when chat selected on wide
for pat in ['min-width: 769','min-width:1024','crm-layout--with-selected .crm-inbox','with-selected.*toolbar']:
    if pat in t or 'with-selected' in t:
        pass
for m in re.finditer(r'@media \(min-width[^)]+\)[^{]*\{[^}]{0,200}crm-inbox[^}]{0,200}\}', t):
    print(m.group()[:300])
print('---')
# hide toolbar when selected on desktop?
for m in re.finditer(r'\.crm-layout--with-selected[^{]*crm-inbox[^{]*\{[^}]+\}', t):
    print(m.group()[:200])
" """,
    timeout=60,
)
print(o.read().decode("utf-8", errors="replace")[:2000])
c.close()
