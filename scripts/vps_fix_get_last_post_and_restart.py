#!/usr/bin/env python3
"""Deploy send_stats fix and restart all active workers on VPS."""
from __future__ import annotations

import os
import socket
import sys
import time
from pathlib import Path

import paramiko

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HOST = "187.127.169.159"
USER = "root"
PASSWORD = os.environ.get("VPS_PASSWORD", "")
REMOTE = "/opt/telegramforward.old"
TF = Path(r"C:\Users\codet\TelegramForward")

FORWARD_SLOTS = ["account1", "account2", "account4", "account6", "account9"]
CAMPAIGN_SLOTS = ["account3", "account5", "account7", "account8", "account10"]

RESTART_REMOTE = f'''
import time, urllib.request, sys
sys.path.insert(0, "/opt/telegramforward.old")
from core.dashboard_auth_vps import get_credentials, create_session_token, SESSION_COOKIE

user, pw = get_credentials()
token = create_session_token(user, role="admin")
FORWARD_SLOTS = {FORWARD_SLOTS!r}
CAMPAIGN_SLOTS = {CAMPAIGN_SLOTS!r}

def post(path):
    req = urllib.request.Request("http://127.0.0.1:8000" + path, method="POST", data=b"")
    req.add_header("Cookie", f"{{SESSION_COOKIE}}={{token}}")
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.read().decode()

def restart_feature(slot, feature):
    try:
        post(f"/account/{{slot}}/stop?feature={{feature}}")
    except Exception as exc:
        print(f"  stop {{slot}} {{feature}}: {{exc}}")
    time.sleep(0.5)
    try:
        post(f"/account/{{slot}}/start?feature={{feature}}")
        print(f"  start {{slot}} {{feature}}: OK")
        return True
    except Exception as exc:
        print(f"  start {{slot}} {{feature}}: FAIL {{exc}}")
        return False

print("=== verify send_stats import ===")
from core.send_stats import get_last_post_timestamp
print("get_last_post_timestamp OK", get_last_post_timestamp("account1"))

print("\\n=== restart forwarding ===")
for slot in FORWARD_SLOTS:
    restart_feature(slot, "forwarding")

print("\\n=== restart campaign ===")
for slot in CAMPAIGN_SLOTS:
    restart_feature(slot, "campaign")
'''


def connect() -> paramiko.SSHClient:
    sock = socket.create_connection((HOST, 22), timeout=30)
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(HOST, username=USER, password=PASSWORD, sock=sock)
    return client


def main() -> None:
    local = TF / "core" / "send_stats.py"
    if not local.exists():
        raise SystemExit(f"Missing {local}")

    client = connect()
    sftp = client.open_sftp()
    remote_path = f"{REMOTE}/core/send_stats.py"
    print("Uploading core/send_stats.py ...")
    sftp.put(str(local), remote_path)
    sftp.close()

    print("Restarting pm2 telegram-backend ...")
    _, stdout, _ = client.exec_command("pm2 restart telegram-backend", timeout=60)
    print(stdout.read().decode("utf-8", errors="replace"))
    time.sleep(5)

    with client.open_sftp() as sftp:
        with sftp.file("/tmp/restart_fleet.py", "w") as f:
            f.write(RESTART_REMOTE)

    print("Restarting fleet workers ...")
    _, stdout, stderr = client.exec_command(
        f"{REMOTE}/venv/bin/python /tmp/restart_fleet.py 2>&1",
        timeout=180,
    )
    print(stdout.read().decode("utf-8", errors="replace"))
    err = stderr.read().decode("utf-8", errors="replace")
    if err.strip():
        print("STDERR:", err)

    print("\n=== post-restart log check ===")
    _, stdout, _ = client.exec_command(
        "pm2 logs telegram-backend --lines 30 --nostream 2>&1 | "
        "grep -E 'get_last_post_timestamp|Shutdown monitor error|Connection failed|wrong session' | tail -15",
        timeout=30,
    )
    print(stdout.read().decode("utf-8", errors="replace") or "(no matching log lines)")
    client.close()
    print("Done.")


if __name__ == "__main__":
    main()
