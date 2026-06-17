"""Deploy internal/external round-wise scope (backend + local static build)."""
from __future__ import annotations

import os
import re
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import paramiko

HOST, USER, REMOTE = "187.127.169.159", "root", "/opt/telegramforward"
PASSWORD = os.environ.get("VPS_PASSWORD", "")
REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STATIC_LOCAL = os.path.join(REPO, "static")

FILES = [
    ("features/candidate_store.py", f"{REMOTE}/features/candidate_store.py"),
    (
        "dashboard/src/candidates/candidatesModule.jsx",
        f"{REMOTE}/dashboard/src/candidates/candidatesModule.jsx",
    ),
]


def upload_tree(sftp: paramiko.SFTPClient, local_root: str, remote_root: str) -> int:
    count = 0
    for dirpath, _dirnames, filenames in os.walk(local_root):
        for name in filenames:
            local = os.path.join(dirpath, name)
            rel = os.path.relpath(local, local_root).replace("\\", "/")
            remote = f"{remote_root}/{rel}"
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
    return count


def main() -> int:
    if not PASSWORD:
        print("VPS_PASSWORD not set", file=sys.stderr)
        return 1

    index_html = os.path.join(STATIC_LOCAL, "index.html")
    if not os.path.isfile(index_html):
        print("Run: cd dashboard && npm run build", file=sys.stderr)
        return 1

    html = open(index_html, encoding="utf-8").read()
    m = re.search(r"/assets/(app-[^\"']+\.js)", html)
    if not m:
        print("index.html missing app bundle", file=sys.stderr)
        return 1
    js_path = os.path.join(STATIC_LOCAL, "assets", m.group(1))
    bundle = open(js_path, encoding="utf-8", errors="replace").read()
    if "Internal (joined org)" not in bundle and "joined org" not in bundle:
        print("Local build missing internal/external round scope UI", file=sys.stderr)
        return 1
    if "Total revenue" not in bundle or "Company revenue" not in bundle:
        print("Local build missing revenue stat cards", file=sys.stderr)
        return 1

    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    print(f"Connecting to {USER}@{HOST}...")
    client.connect(HOST, username=USER, password=PASSWORD, timeout=30)
    sftp = client.open_sftp()

    for rel, remote in FILES:
        local = os.path.join(REPO, rel.replace("/", os.sep))
        print(f"upload {rel}")
        sftp.put(local, remote)

    print("upload static/ tree...")
    n = upload_tree(sftp, STATIC_LOCAL, f"{REMOTE}/static")
    print(f"  {n} static files")
    sftp.close()

    for cmd in [
        "pm2 restart telegram-backend 2>/dev/null || true",
        "curl -s http://127.0.0.1:8000/health | head -c 200",
    ]:
        print(f"\n>>> {cmd}")
        _stdin, stdout, stderr = client.exec_command(cmd, timeout=60)
        out = stdout.read().decode("utf-8", errors="replace")
        if out:
            print(out.strip())

    client.close()
    print("\nRound scope deploy done.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
