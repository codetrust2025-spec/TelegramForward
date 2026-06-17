"""Sync Python backend from /opt/telegramforward to /opt/telegramforward.old and restart PM2."""
import os
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import paramiko

HOST, USER = "187.127.169.159", "root"
PWD = os.environ.get("VPS_PASSWORD", "")
SRC, DST = "/opt/telegramforward", "/opt/telegramforward.old"
FILES = [
    "core/posting_mode.py",
    "features/interval_forward.py",
    "workers/account_worker.py",
    "server.py",
    "services/account_manager.py",
]

cmds = [
    f"for f in {' '.join(FILES)}; do cp -a {SRC}/$f {DST}/$f; done",
    f"python3 -c \"import sys; sys.path.insert(0,'{DST}'); "
    f"from core.posting_mode import SOURCE_TEMPLATE; print('old_backend', SOURCE_TEMPLATE)\"",
    "pm2 restart telegram-backend",
    "sleep 2 && curl -sf http://127.0.0.1:8000/health | head -c 200",
]

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(HOST, username=USER, password=PWD, timeout=30)
for cmd in cmds:
    print(">>>", cmd)
    _, o, e = c.exec_command(cmd, timeout=120)
    code = o.channel.recv_exit_status()
    print(o.read().decode("utf-8", errors="replace"))
    err = e.read().decode("utf-8", errors="replace")
    if err:
        print("stderr:", err)
    print("exit", code)
    if code != 0:
        sys.exit(code)
c.close()
print("sync ok")
