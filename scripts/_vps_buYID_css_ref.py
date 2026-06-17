import os
import paramiko

PWD = os.environ.get("VPS_PASSWORD", "")
c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect("187.127.169.159", username="root", password=PWD, timeout=30)
_, o, _ = c.exec_command(
    "python3 -c \"import pathlib; t=pathlib.Path('/opt/telegramforward/static/assets/index-buYID2R_.js').read_text('utf-8',errors='replace'); "
    "print('css refs', [x for x in ['index-','.css'] if x in t[:5000]]); "
    "import re; print(re.findall(r'index-[A-Za-z0-9_-]+\\.css', t)[:5])\""
)
print(o.read().decode("utf-8", "replace"))
_, o, _ = c.exec_command("ls -la /opt/telegramforward/static/assets/index-CuMYH96d.css 2>/dev/null")
print(o.read().decode("utf-8", "replace"))
c.close()
