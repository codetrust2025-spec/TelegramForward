"""Deploy active candidates roster (API + dashboard viewer + CSV)."""
from __future__ import annotations

import os
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HOST = "187.127.169.159"
USER = "root"
REMOTES = ["/opt/telegramforward", "/opt/telegramforward.old"]
PASSWORD = os.environ.get("VPS_PASSWORD", "")
BUILD_STAMP = "2026-06-05-candidates-roster"


def put_tree(sftp, local_dir: str, remote_dir: str) -> None:
    for name in os.listdir(local_dir):
        lp = os.path.join(local_dir, name)
        rp = f"{remote_dir}/{name}"
        if os.path.isdir(lp):
            try:
                sftp.stat(rp)
            except OSError:
                sftp.mkdir(rp)
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
        "server.py",
        "features/candidate_store.py",
        "dashboard/src/config.js",
        "dashboard/src/index.css",
        "dashboard/src/candidates/candidatesModule.jsx",
        "dashboard/src/candidates/CandidatesActiveRoster.jsx",
        "dashboard/src/candidates/candidatesRosterUtils.js",
    ]

    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(HOST, username=USER, password=PASSWORD, timeout=30)
    sftp = client.open_sftp()

    for remote in REMOTES:
        for rel in files:
            local = os.path.join(repo, rel.replace("/", os.sep))
            remote_path = f"{remote}/{rel}".replace("\\", "/")
            sftp.put(local, remote_path)
            print(f"  {remote}: {rel}")
        put_tree(sftp, static, f"{remote}/static")

    sftp.close()
    client.exec_command(
        "rsync -a --delete /opt/telegramforward.old/static/ /opt/telegramforward/static/; "
        "pm2 restart telegram-backend --update-env",
        timeout=60,
    )
    _, o, _ = client.exec_command(
        f"grep -o '{BUILD_STAMP}' /opt/telegramforward/static/assets/app-*.js | head -1; "
        "curl -s 'http://127.0.0.1:8000/candidates/roster' | head -c 120",
        timeout=30,
    )
    print(o.read().decode().strip())
    client.close()
    print(f"Done — hard refresh (stamp {BUILD_STAMP})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
