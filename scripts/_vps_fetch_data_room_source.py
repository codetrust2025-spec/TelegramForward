import os
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
import paramiko

PWD = os.environ.get("VPS_PASSWORD", "")
REMOTE = "/opt/telegramforward"
LOCAL = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect("187.127.169.159", username="root", password=PWD, timeout=30)

# Try to pull teleautomation-app.jsx if present
_, o, _ = c.exec_command(f"test -f {REMOTE}/dashboard/src/teleautomation-app.jsx && wc -l {REMOTE}/dashboard/src/teleautomation-app.jsx")
print(o.read().decode())

sftp = c.open_sftp()
try:
    remote = f"{REMOTE}/dashboard/src/teleautomation-app.jsx"
    local = os.path.join(LOCAL, "scripts", "_vps_extract", "teleautomation-app-vps.jsx")
    sftp.get(remote, local)
    print("fetched teleautomation-app-vps.jsx")
except Exception as e:
    print("no teleautomation-app.jsx", e)

# Extract snippet from dashboard.bundle.js
_, o, _ = c.exec_command(
    f"python3 -c \""
    f"import pathlib\n"
    f"p=pathlib.Path('{REMOTE}/static/assets/dashboard.bundle.js')\n"
    f"t=p.read_text('utf-8', errors='replace')\n"
    f"i=t.find('dr-vault-block')\n"
    f"print(t[max(0,i-3000):i+8000])\n"
    f"\""
)
out = o.read().decode("utf-8", "replace")
path = os.path.join(LOCAL, "scripts", "_vps_extract", "data_room_bundle_snippet.txt")
with open(path, "w", encoding="utf-8") as f:
    f.write(out)
print("wrote snippet", len(out))

sftp.close()
c.close()
