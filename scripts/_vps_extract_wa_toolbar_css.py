import os
import paramiko

PWD = os.environ.get("VPS_PASSWORD", "")
c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect("187.127.169.159", username="root", password=PWD, timeout=30)
_, o, _ = c.exec_command(
    r"""python3 -c "
import re
p='/opt/telegramforward/dashboard/src/teleautomation.css'
try:
    t=open(p).read()
except FileNotFoundError:
    t=''
    p='/opt/telegramforward/dashboard/src/index.css'
    t=open(p).read()
for key in ['crm-inbox-toolbar','call-analytics','inbox-root--chat-open','wa-chat-header']:
    for m in re.finditer(r'[^{}]{0,60}'+re.escape(key)+r'[^{}]{0,80}\{[^}]+\}', t):
        print(m.group()[:220])
        print('---')
" """,
    timeout=60,
)
print(o.read().decode("utf-8", errors="replace")[:8000])
c.close()
