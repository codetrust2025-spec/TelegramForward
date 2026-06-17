import os
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
    "for name in ['dashboard.bundle.js','index-buYID2R_.js']:\n"
    " p=pathlib.Path('/opt/telegramforward/static/assets')/name\n"
    " if not p.exists(): continue\n"
    " t=p.read_text('utf-8', errors='replace')\n"
    " for needle in ['Vault','dr-vault-block','Service accounts','Offer letters','Key links','Business opportunities']:\n"
    "  print(name, needle, needle in t)\n"
    "\""
)
print(o.read().decode())
c.close()
