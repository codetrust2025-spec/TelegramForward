"""Deploy voice_call_api routes to production backend."""
from __future__ import annotations

import os
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import paramiko

HOST, USER, REMOTE = "187.127.169.159", "root", "/opt/telegramforward.old"
PWD = os.environ.get("VPS_PASSWORD", "")
LOCAL_API = os.path.join(
    os.path.dirname(os.path.dirname(__file__)), "core", "voice_call_api.py"
)
SERVER = f"{REMOTE}/server.py"

INSTALL_BLOCK = """
from core.voice_call_api import install_voice_call_routes
install_voice_call_routes(app)
"""

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(HOST, username=USER, password=PWD, timeout=30)

sftp = c.open_sftp()
sftp.put(LOCAL_API, f"{REMOTE}/core/voice_call_api.py")
print("uploaded voice_call_api.py")
sftp.close()

_, o, _ = c.exec_command(f"cat {SERVER}", timeout=60)
content = o.read().decode("utf-8", errors="replace")

if "install_voice_call_routes" not in content:
    marker = "install_web_push_routes(app)"
    if marker not in content:
        raise SystemExit("install_web_push_routes(app) not found in server.py")
    content = content.replace(
        marker,
        marker + INSTALL_BLOCK,
        1,
    )
    print("wired install_voice_call_routes in server.py")
else:
    print("voice routes already wired")

old_roots = '"devices", "demo-tools", "workspace"}'
new_roots = '"devices", "demo-tools", "workspace", "voice"}'
if old_roots in content:
    content = content.replace(old_roots, new_roots, 1)
    print("added voice to api_roots")
elif '"voice"}' in content or "'voice'" in content:
    print("voice already in api_roots")
else:
    print("WARN: could not patch api_roots — check serve_spa manually")

sftp = c.open_sftp()
with sftp.open(SERVER, "w") as f:
    f.write(content.encode("utf-8"))
sftp.close()

for cmd in [
    f"cd {REMOTE} && python3 -c \"from core.voice_call_api import install_voice_call_routes; print('import ok')\"",
    "pm2 restart telegram-backend",
    "sleep 2",
    'curl -s -o /dev/null -w "voice:%{http_code} %{content_type}\\n" "http://127.0.0.1:8000/voice/analytics?days=30"',
    'curl -s "http://127.0.0.1:8000/voice/analytics?days=30" | head -c 120',
    'curl -s -o /dev/null -w "analytics:%{http_code} %{content_type}\\n" "http://127.0.0.1:8000/analytics?days=30"',
]:
    print(">>>", cmd[:90])
    _, o, e = c.exec_command(cmd, timeout=90)
    print(o.read().decode("utf-8", errors="replace")[:400])
    err = e.read().decode("utf-8", errors="replace")
    if err.strip():
        print("ERR:", err[:300])

c.close()
print("done")
