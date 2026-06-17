"""Fix interview APIs + restore original monolith Daily ops UI on production."""
from __future__ import annotations

import os
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import paramiko

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HOST, USER, REMOTE = "187.127.169.159", "root", "/opt/telegramforward"
PASSWORD = os.environ.get("VPS_PASSWORD", "")


def main() -> int:
    if not PASSWORD:
        print("VPS_PASSWORD required", file=sys.stderr)
        return 1

    src = os.path.join(REPO, "scripts", "_vps_candidate_store.py")
    dst = os.path.join(REPO, "features", "candidate_store.py")
    if "interview_upcoming" not in open(dst, encoding="utf-8").read():
        import shutil
        shutil.copy2(src, dst)
        print(f"Synced candidate_store.py ({sum(1 for _ in open(dst))} lines)")

    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(HOST, username=USER, password=PASSWORD, timeout=30)
    sftp = client.open_sftp()

    for rel in ("features/candidate_store.py", "server.py"):
        local = os.path.join(REPO, rel)
        remote = f"{REMOTE}/{rel}"
        sftp.put(local, remote)
        print(f"uploaded {rel}")

    sftp.close()

    _, o, _ = client.exec_command(
        f"grep -c interview_upcoming {REMOTE}/features/candidate_store.py && "
        f"cd {REMOTE} && pm2 restart telegram-backend --update-env 2>&1 | tail -3"
    )
    print(o.read().decode("utf-8", errors="replace"))

    # Restore full monolith bundle + module index.html (original Daily ops UI)
    env = {**os.environ, "VPS_PASSWORD": PASSWORD}
    subprocess.check_call(
        [sys.executable, os.path.join(REPO, "scripts", "_fix_bundle_module.py")],
        env=env,
    )

    client.close()
    print("Done — hard refresh teleautomation.online")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
