#!/usr/bin/env python3
"""Upload patched app bundle only (preserves production index.html)."""
import os, socket, sys
from pathlib import Path
import paramiko

from _deploy_common import enforce_git_first

enforce_git_first()

PASSWORD = os.environ.get("VPS_PASSWORD", "")
LOCAL = Path(__file__).resolve().parent.parent / "static" / "assets" / "app-BkUk1ts9.js"
REMOTE = "/opt/telegramforward/static/assets/app-BkUk1ts9.js"

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

sock = socket.create_connection(("187.127.169.159", 22), timeout=30)
c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(hostname="187.127.169.159", username="root", password=PASSWORD, sock=sock)
sftp = c.open_sftp()

# backup remote
try:
    st = sftp.stat(REMOTE)
    backup = REMOTE.replace(".js", f".bak_login_fix.js")
    with sftp.open(REMOTE, "rb") as rf, sftp.open(backup, "wb") as wf:
        wf.write(rf.read())
    print(f"Backup: {backup} ({st.st_size} bytes)")
except Exception as e:
    print(f"Backup skip: {e}")

sftp.put(str(LOCAL), REMOTE)
st2 = sftp.stat(REMOTE)
print(f"Uploaded {LOCAL.name} -> {REMOTE} ({st2.st_size} bytes)")

# verify index references this bundle
ch = c.get_transport().open_session()
ch.exec_command("grep -o 'app-[^\"]*\\.js' /opt/telegramforward/static/index.html; curl -s -o /dev/null -w 'HTTP %{http_code}\\n' http://127.0.0.1:8000/")
out = b""
while ch.recv_ready() or not ch.exit_status_ready():
    if ch.recv_ready():
        out += ch.recv(65535)
    if ch.exit_status_ready() and not ch.recv_ready():
        break
print(out.decode("utf-8", "replace"))
sftp.close()
c.close()
print("Done — hard refresh teleautomation.online")
