import os
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
import paramiko

PWD = os.environ.get("VPS_PASSWORD", "")
c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect("187.127.169.159", username="root", password=PWD, timeout=30)
cmd = (
    "python3 -c \"import sys; sys.path.insert(0,'/opt/telegramforward'); "
    "from core.posting_mode import SOURCE_TEMPLATE, load_posting_mode; "
    "d=load_posting_mode('account3').to_dict('account3'); "
    "print('source_type', d['forwarding'].get('source_type')); "
    "print('configured_keys', list(d['forwarding'].keys()))\""
)
_, o, e = c.exec_command(cmd, timeout=30)
print(o.read().decode())
print(e.read().decode())
c.close()
