import os
import paramiko

PWD = os.environ.get("VPS_PASSWORD", "")
c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect("187.127.169.159", username="root", password=PWD, timeout=30)
_, o, _ = c.exec_command(
    r"""python3 -c "
t=open('/opt/telegramforward/dashboard/src/teleautomation-app.jsx').read()
i=t.find('crm-inbox-toolbar')
chunk=t[i:i+2500]
print(chunk[:2500])
" """,
    timeout=60,
)
print(o.read().decode("utf-8", errors="replace"))
c.close()
