"""Deploy inbox hold-to-record voice composer."""
from __future__ import annotations

import os
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HOST = "187.127.169.159"
USER = "root"
REMOTES = ["/opt/telegramforward", "/opt/telegramforward.old"]
PASSWORD = os.environ.get("VPS_PASSWORD", "")
BUILD_STAMP = "2026-06-05-voice-record"


def put_tree(sftp, local_dir: str, remote_dir: str) -> None:
    for name in os.listdir(local_dir):
        lp = os.path.join(local_dir, name)
        rp = f"{remote_dir}/{name}"
        if os.path.isdir(lp):
            try:
                sftp.stat(rp)
            except OSError:
                try:
                    sftp.mkdir(rp)
                except OSError:
                    pass
            put_tree(sftp, lp, rp)
        else:
            sftp.put(lp, rp)


def main() -> int:
    if not PASSWORD:
        print("VPS_PASSWORD not set", file=sys.stderr)
        return 1

    import paramiko

    repo = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    dash = os.path.join(repo, "dashboard")
    static = os.path.join(repo, "static")

    subprocess.run(["npm", "run", "build"], cwd=dash, shell=os.name == "nt", check=True)

    files = [
        "dashboard/src/config.js",
        "dashboard/src/inbox/ChatComposer.jsx",
        "dashboard/src/inbox/useVoiceRecorder.js",
        "dashboard/src/inbox/inboxUiUtils.js",
        "dashboard/src/inbox/inboxLayout.css",
    ]

    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(HOST, username=USER, password=PASSWORD, timeout=30)
    sftp = client.open_sftp()
    for remote in REMOTES:
        for rel in files:
            sftp.put(os.path.join(repo, rel.replace("/", os.sep)), f"{remote}/{rel}")
        put_tree(sftp, static, f"{remote}/static")
        print(f"uploaded {remote}")
    sftp.close()
    client.exec_command(
        "rsync -a --delete /opt/telegramforward.old/static/ /opt/telegramforward/static/",
        timeout=120,
    )
    _, o, _ = client.exec_command(
        f"grep -o '{BUILD_STAMP}' /opt/telegramforward/static/assets/app-*.js | head -1",
        timeout=30,
    )
    print("stamp:", o.read().decode().strip())
    client.close()
    print("Done — hard refresh ?hard=1")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
