import os
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
import paramiko

PWD = os.environ.get("VPS_PASSWORD", "")
c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect("187.127.169.159", username="root", password=PWD, timeout=30)
_, o, _ = c.exec_command(
    "grep -l 'dr-vault-block' /opt/telegramforward/static/assets/*.css 2>/dev/null | head -1"
)
css_file = o.read().decode().strip()
print("css:", css_file)
if css_file:
    _, o, _ = c.exec_command(
        f"python3 -c \"import pathlib; t=pathlib.Path('{css_file}').read_text('utf-8',errors='replace'); "
        "i=t.find('.dr-vault-block'); print(t[i:i+12000] if i>=0 else 'NO')\""
    )
    out = o.read().decode("utf-8", "replace")
    local = os.path.join(os.path.dirname(os.path.dirname(__file__)), "scripts", "_vps_extract", "dr_vault.css")
    with open(local, "w", encoding="utf-8") as f:
        f.write(out)
    print("wrote", local, len(out))
c.close()
