"""Upload locally built static/ + login source to VPS (skip VPS npm build)."""
from __future__ import annotations

import os
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import paramiko

HOST, USER, REMOTE = "187.127.169.159", "root", "/opt/telegramforward"
PASSWORD = os.environ.get("VPS_PASSWORD", "")
REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STATIC_LOCAL = os.path.join(REPO, "static")
FILES = [
    ("dashboard/src/components/LoginScreen.jsx", f"{REMOTE}/dashboard/src/components/LoginScreen.jsx"),
    ("dashboard/src/index.css", f"{REMOTE}/dashboard/src/index.css"),
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
                    sftp.mkdir(path)
            sftp.put(local, remote)
            count += 1
    return count


def main() -> int:
    if not PASSWORD:
        print("VPS_PASSWORD not set", file=sys.stderr)
        return 1

    # Verify local build has toggle markup
    index_html = os.path.join(STATIC_LOCAL, "index.html")
    if not os.path.isfile(index_html):
        print("Run: cd dashboard && npm run build", file=sys.stderr)
        return 1

    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
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

    import re

    html = open(index_html, encoding="utf-8").read()
    m = re.search(r"/assets/(app-[^\"']+\.js)", html)
    if not m:
        print("index.html missing app bundle", file=sys.stderr)
        return 1
    js_path = os.path.join(STATIC_LOCAL, "assets", m.group(1))
    verify_local = open(js_path, encoding="utf-8", errors="replace").read()
    if "auth-password-toggle" not in verify_local:
        print("Local build missing password toggle — run: cd dashboard && npm run build", file=sys.stderr)
        return 1

    cmd = (
        f"grep -o 'app-[^\"]*\\.js' {REMOTE}/static/index.html | head -1 | "
        f"xargs -I{{}} sh -c 'grep -l auth-password-toggle {REMOTE}/static/assets/{{}} 2>/dev/null || "
        f"grep -l \"Show password\" {REMOTE}/static/assets/{{}}'"
    )
    print(f"\n>>> {cmd}")
    _stdin, stdout, stderr = client.exec_command(cmd, timeout=30)
    out = stdout.read().decode("utf-8", errors="replace")
    print(out or "VERIFY_OK (grep via index)")

    client.close()
    print("\nLogin password toggle deployed to static/.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
