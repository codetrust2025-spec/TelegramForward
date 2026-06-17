"""Deploy Total List header button (dashboard static bundle)."""
from __future__ import annotations

import os
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HOST = "187.127.169.159"
USER = "root"
REMOTES = ["/opt/telegramforward", "/opt/telegramforward.old"]
PASSWORD = os.environ.get("VPS_PASSWORD", "")


def ensure_remote_dir(sftp, remote_dir: str) -> None:
    parts = remote_dir.strip("/").split("/")
    path = ""
    for p in parts:
        path += f"/{p}"
        try:
            sftp.stat(path)
        except OSError:
            try:
                sftp.mkdir(path)
            except OSError:
                pass


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

    print(">>> npm run build (local)")
    r = subprocess.run(
        ["npm", "run", "build"],
        cwd=dash,
        shell=os.name == "nt",
        check=False,
    )
    if r.returncode != 0:
        print("local build failed", file=sys.stderr)
        return r.returncode

    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    print(f"Connecting to {USER}@{HOST}...")
    client.connect(HOST, username=USER, password=PASSWORD, timeout=30)
    sftp = client.open_sftp()

    source_files = [
        "dashboard/src/App.jsx",
        "dashboard/src/config.js",
        "dashboard/src/index.css",
        "dashboard/src/inbox/ChatHeader.jsx",
        "dashboard/src/inbox/inboxLayout.css",
        "dashboard/src/desktop/DesktopApp.jsx",
        "dashboard/src/desktop/DesktopHeader.jsx",
        "dashboard/src/desktop/DesktopSidebar.jsx",
        "dashboard/src/desktop/desktopDashboard.css",
        "dashboard/src/mobile/MobileApp.jsx",
        "dashboard/src/mobile/mobileDashboard.css",
    ]

    for remote in REMOTES:
        print(f"\n=== {remote} ===")
        for rel in source_files:
            local = os.path.join(repo, rel.replace("/", os.sep))
            remote_path = f"{remote}/{rel}".replace("\\", "/")
            ensure_remote_dir(sftp, os.path.dirname(remote_path).replace("\\", "/"))
            sftp.put(local, remote_path)
            print(f"  uploaded {rel}")
        put_tree(sftp, static, f"{remote}/static")
        print("  uploaded static/")

    sftp.close()

    _, o, _ = client.exec_command(
        "grep -o '2026-06-05-brand-dashboard' /opt/telegramforward/static/assets/app-*.js | head -1; "
        "ls -t /opt/telegramforward/static/assets/app-*.js | head -1",
        timeout=30,
    )
    print("\nVerify:", o.read().decode().strip())

    _, o3, _ = client.exec_command(
        "rsync -a --delete /opt/telegramforward.old/static/ /opt/telegramforward/static/",
        timeout=120,
    )
    print("nginx static sync:", o3.read().decode().strip()[-200:])

    _, o2, _ = client.exec_command(
        "pm2 restart telegram-backend --update-env 2>/dev/null || true",
        timeout=45,
    )
    print("pm2:", o2.read().decode().strip()[-300:])

    client.close()
    print("\nDeployed — hard refresh https://teleautomation.online?hard=1")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
