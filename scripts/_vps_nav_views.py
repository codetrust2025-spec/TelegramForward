import os
import re
import paramiko

PWD = os.environ.get("VPS_PASSWORD", "")
c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect("187.127.169.159", username="root", password=PWD, timeout=30)
_, o, _ = c.exec_command(
    r"""python3 -c "import pathlib,re; t=pathlib.Path('/opt/telegramforward/static/assets/dashboard.bundle.js').read_text('utf-8','replace');
[print(v,l) for v,l in re.findall(r'value:\"([^\"]+)\"[^}]{0,80}label:\"([^\"]+)\"', t) if 'daily' in v or 'ops' in l.lower() or v in ('dashboard','inbox','candidates','data-room','admin','logs')]" """
)
print(o.read().decode("utf-8", "replace"))
c.close()
