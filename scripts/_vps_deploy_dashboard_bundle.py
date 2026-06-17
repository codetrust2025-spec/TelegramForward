"""Build dashboard locally and upload static/ bundle to VPS (fixes bad remote builds)."""
from __future__ import annotations

import os
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HOST = "187.127.169.159"
USER = "root"
REMOTE = "/opt/telegramforward.old"
PASSWORD = os.environ.get("VPS_PASSWORD", "")


def main() -> int:
    if not PASSWORD:
        print("VPS_PASSWORD not set", file=sys.stderr)
        return 1

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
        return r.returncode

    import paramiko

    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    print(f"Connecting to {USER}@{HOST}...")
    client.connect(HOST, username=USER, password=PASSWORD, timeout=30)
    sftp = client.open_sftp()

    backend_files = [
        "core/ist_time.py",
        "core/account_shutdown.py",
        "core/joined_membership.py",
        "core/stats_reset.py",
        "core/ai_smart_reply.py",
        "core/karthik_economy_preset.py",
        "core/ai_smart_reply_store.py",
        "core/dm_store.py",
        "services/dm_inbox_service.py",
        "messaging/message_router.py",
        "workers/account_worker.py",
        "server.py",
        "features/telegram_joined_stats.py",
        "features/inbox_export.py",
        "data/ai_smart_reply.json",
    ]
    for rel in backend_files:
        local = os.path.join(repo, rel.replace("/", os.sep))
        remote = f"{REMOTE}/{rel}".replace("\\", "/")
        print(f"  upload {rel}")
        sftp.put(local, remote)

    uploads = ["index.html"]
    assets_dir = os.path.join(static, "assets")
    if os.path.isdir(assets_dir):
        for name in os.listdir(assets_dir):
            uploads.append(f"assets/{name}")

    for rel in uploads:
        local = os.path.join(static, rel.replace("/", os.sep))
        remote = f"{REMOTE}/static/{rel}".replace("\\", "/")
        remote_dir = os.path.dirname(remote)
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
        print(f"  upload static/{rel}")
        sftp.put(local, remote)

    sftp.close()

    _, o, _ = client.exec_command(
        f"head -3 {REMOTE}/static/index.html && ls -la {REMOTE}/static/assets/*.js | tail -3",
        timeout=30,
    )
    print("\nVerify:", o.read().decode().strip())
    _, o2, _ = client.exec_command("pm2 restart telegram-backend", timeout=45)
    print("\npm2:", o2.read().decode().strip()[-400:])
    nginx_static = "/opt/telegramforward/static"
    _, o3, _ = client.exec_command(
        f"rsync -a --delete {REMOTE}/static/ {nginx_static}/",
        timeout=120,
    )
    print("\nnginx static sync:", o3.read().decode().strip()[-200:])
    client.close()
    print("\nDashboard bundle deployed — hard refresh https://teleautomation.online")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
