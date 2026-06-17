import os
import pathlib
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
import paramiko

PWD = os.environ.get("VPS_PASSWORD", "")
c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect("187.127.169.159", username="root", password=PWD, timeout=30)
_, o, _ = c.exec_command(
    "python3 -c \"import pathlib; t=pathlib.Path('/opt/telegramforward/static/assets/dashboard.bundle.js').read_text('utf-8',errors='replace'); "
    "i=t.find('dr-tabs'); print('idx',i); print(t[i:i+2500] if i>=0 else t[t.find('logins'):t.find('logins')+2500])\""
)
print(o.read().decode("utf-8", "replace")[:3000])
c.close()
