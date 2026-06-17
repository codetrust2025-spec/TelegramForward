import os
import paramiko

PWD = os.environ.get("VPS_PASSWORD", "")
c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect("187.127.169.159", username="root", password=PWD, timeout=30)
_, o, _ = c.exec_command(
    "grep -o 'inbox-root--chat-open[^\"]*' /opt/telegramforward/dashboard/src/teleautomation-app.jsx | head -5; "
    "grep -o 'crm-layout--with-selected[^\"]*' /opt/telegramforward/dashboard/src/teleautomation-app.jsx | head -5; "
    r"""node -e "
import re
t=open('/opt/telegramforward/dashboard/src/teleautomation-app.jsx').read()
m=re.search(r'inbox-root crm-root wa-inbox.{0,120}', t)
print('root class', m.group(0) if m else 'nf')
m2=re.search(r'crm-layout inbox-layout.{0,80}', t)
print('layout', m2.group(0) if m2 else 'nf')
" """,
    timeout=60,
)
print(o.read().decode("utf-8", errors="replace"))
c.close()
