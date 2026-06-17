"""Deploy economy preset (backend + dashboard static)."""
from __future__ import annotations

import os
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HOST = "187.127.169.159"
USER = "root"
REMOTE = "/opt/telegramforward.old"
PASSWORD = os.environ.get("VPS_PASSWORD", "")

BACKEND = [
    "core/karthik_economy_preset.py",
    "core/ai_smart_reply_store.py",
    "server.py",
]


def main() -> int:
    if not PASSWORD:
        print("VPS_PASSWORD not set", file=sys.stderr)
        return 1

    repo = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    dash = os.path.join(repo, "dashboard")
    static = os.path.join(repo, "static")

    print(">>> npm run build")
    r = subprocess.run(["npm", "run", "build"], cwd=dash, shell=os.name == "nt", check=False)
    if r.returncode != 0:
        return r.returncode

    import paramiko

    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    print(f"Connecting to {USER}@{HOST}...")
    client.connect(HOST, username=USER, password=PASSWORD, timeout=30)
    sftp = client.open_sftp()

    for rel in BACKEND:
        local = os.path.join(repo, rel.replace("/", os.sep))
        remote = f"{REMOTE}/{rel}".replace("\\", "/")
        print(f"  upload {rel}")
        sftp.put(local, remote)

    for rel in ["index.html"]:
        assets = os.path.join(static, "assets")
        if os.path.isdir(assets):
            for name in os.listdir(assets):
                rel = f"assets/{name}"
                local = os.path.join(static, rel.replace("/", os.sep))
                remote = f"{REMOTE}/static/{rel}".replace("\\", "/")
                print(f"  upload static/{rel}")
                sftp.put(local, remote)

    local_index = os.path.join(static, "index.html")
    sftp.put(local_index, f"{REMOTE}/static/index.html")

    sftp.close()
    _, o, _ = client.exec_command("pm2 restart telegram-backend", timeout=45)
    print("pm2:", o.read().decode().strip()[-200:])
    client.close()
    print("Economy preset deployed — Admin → AI controls → Apply Economy preset")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
