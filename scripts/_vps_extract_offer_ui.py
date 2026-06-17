import os
import re
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
import paramiko

PWD = os.environ.get("VPS_PASSWORD", "")
c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect("187.127.169.159", username="root", password=PWD, timeout=30)
_, o, _ = c.exec_command(
    "python3 -c \""
    "import pathlib\n"
    "p=pathlib.Path('/opt/telegramforward/static/assets')\n"
    "for f in sorted(p.glob('*.js'), key=lambda x: -x.stat().st_size)[:3]:\n"
    " t=f.read_text('utf-8', errors='replace')\n"
    " if 'Offer letters' in t:\n"
    "  i=t.index('Offer letters')\n"
    "  print('FILE', f.name, 'LEN', len(t))\n"
    "  print(t[max(0,i-500):i+2500])\n"
    "  break\n"
    "\""
)
print(o.read().decode("utf-8", "replace"))
c.close()
