"""Download monolith bundle, build daily ops module, deploy backend + static."""
from __future__ import annotations

import os
import shutil
import subprocess
import sys

import paramiko

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HOST, USER, REMOTE = "187.127.169.159", "root", "/opt/telegramforward"
PASSWORD = os.environ.get("VPS_PASSWORD", "")


def download_bundle(sftp: paramiko.SFTPClient) -> str:
    remote = f"{REMOTE}/static/assets/dashboard.bundle.js"
    local = os.path.join(REPO, "static", "assets", "dashboard.bundle.js")
    os.makedirs(os.path.dirname(local), exist_ok=True)
    sftp.get(remote, local)
    return local


def upload_files(sftp: paramiko.SFTPClient, pairs: list[tuple[str, str]]) -> int:
    n = 0
    for local, remote_rel in pairs:
        remote = f"{REMOTE}/{remote_rel.replace(chr(92), '/')}"
        sftp.put(local, remote)
        n += 1
        print(f"  uploaded {remote_rel}")
    return n


def main() -> int:
    if not PASSWORD:
        print("VPS_PASSWORD required", file=sys.stderr)
        return 1

    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(HOST, username=USER, password=PASSWORD, timeout=30)
    sftp = client.open_sftp()

    print("Downloading monolith bundle…")
    bundle_path = download_bundle(sftp)
    print(f"  {bundle_path} ({os.path.getsize(bundle_path)} bytes)")

    print("Building dailyOpsModule.core.js…")
    subprocess.check_call([sys.executable, os.path.join(REPO, "scripts", "_build_daily_ops_module.py")])

    core = os.path.join(REPO, "dashboard", "src", "dailyOps", "dailyOpsModule.core.js")
    if not os.path.isfile(core):
        print("dailyOpsModule.core.js missing", file=sys.stderr)
        return 1
    print(f"  core module {os.path.getsize(core)} bytes")

    print("Extracting daily ops CSS…")
    subprocess.check_call([sys.executable, os.path.join(REPO, "scripts", "_extract_daily_ops_css.py")])

    print("Building dashboard…")
    subprocess.check_call("npm run build", cwd=os.path.join(REPO, "dashboard"), shell=True)

    print("Uploading backend…")
    upload_files(
        sftp,
        [
            (os.path.join(REPO, "server.py"), "server.py"),
            (os.path.join(REPO, "features", "candidate_store.py"), "features/candidate_store.py"),
        ],
    )

    print("Uploading static/…")
    static_local = os.path.join(REPO, "static")
    count = 0
    for dirpath, _dirnames, filenames in os.walk(static_local):
        for name in filenames:
            local = os.path.join(dirpath, name)
            rel = os.path.relpath(local, static_local).replace("\\", "/")
            remote = f"{REMOTE}/static/{rel}"
            remote_dir = os.path.dirname(remote).replace("\\", "/")
            parts = remote_dir.split("/")
            path = ""
            for p in parts:
                if not p:
                    continue
                path += f"/{p}"
                try:
                    sftp.stat(path)
                except OSError:
                    try:
                        sftp.mkdir(path)
                    except OSError:
                        pass
            sftp.put(local, remote)
            count += 1
    print(f"  {count} static files")

    print("Restarting backend…")
    _, stdout, stderr = client.exec_command(f"cd {REMOTE} && pm2 restart telegram-backend --update-env 2>&1")
    print(stdout.read().decode("utf-8", errors="replace"))
    err = stderr.read().decode("utf-8", errors="replace")
    if err:
        print(err, file=sys.stderr)

    sftp.close()
    client.close()
    print("Done.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
