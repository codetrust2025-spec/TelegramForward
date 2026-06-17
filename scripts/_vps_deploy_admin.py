"""Deploy Admin tab UI + wire /admin/dashboard on VPS."""
from __future__ import annotations

import os
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HOST, USER = "187.127.169.159", "root"
REMOTE = "/opt/telegramforward"
REMOTE_OLD = "/opt/telegramforward.old"
PWD = os.environ.get("VPS_PASSWORD", "")
REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

FILES = [
    "dashboard/src/App.jsx",
    "dashboard/src/main.jsx",
    "dashboard/src/admin.css",
    "dashboard/src/components/AdminPanel.jsx",
    "dashboard/src/admin/adminModule.jsx",
]


def wire_server(sftp, client) -> None:
    for base in (REMOTE_OLD, REMOTE):
        try:
            with sftp.open(f"{base}/server.py", "r") as f:
                server = f.read().decode("utf-8")
        except OSError:
            continue
        needle = "install_dashboard_auth(app)"
        if "install_admin_dashboard" in server:
            print(f"  server already wired: {base}")
            break
        if needle not in server:
            # append near app creation if no auth install
            if "app = FastAPI" in server and "install_admin_dashboard" not in server:
                insert = (
                    "\nfrom core.admin_dashboard import install_admin_dashboard\n"
                    "install_admin_dashboard(app)\n"
                )
                if insert.strip() not in server:
                    server = server.replace("app = FastAPI()", "app = FastAPI()" + insert, 1)
                    with sftp.open(f"{base}/server.py", "w") as f:
                        f.write(server.encode("utf-8"))
                    print(f"  appended install_admin_dashboard to {base}/server.py")
            continue
        server = server.replace(
            needle,
            needle
            + "\n\nfrom core.admin_dashboard import install_admin_dashboard\ninstall_admin_dashboard(app)",
            1,
        )
        with sftp.open(f"{base}/server.py", "w") as f:
            f.write(server.encode("utf-8"))
        print(f"  wired {base}/server.py")
        break

    # Ensure admin_dashboard.py on both paths
    local_admin = os.path.join(REPO, "core", "admin_dashboard.py")
    if os.path.isfile(local_admin):
        for base in (REMOTE_OLD, REMOTE):
            try:
                sftp.put(local_admin, f"{base}/core/admin_dashboard.py")
                print(f"  uploaded core/admin_dashboard.py -> {base}")
            except OSError as e:
                print(f"  skip {base}: {e}")
    else:
        try:
            sftp.get(f"{REMOTE_OLD}/core/admin_dashboard.py", local_admin)
            sftp.put(local_admin, f"{REMOTE}/core/admin_dashboard.py")
            print("  synced admin_dashboard.py from .old")
        except OSError as e:
            print("  warn: no local admin_dashboard.py", e)

    _, o, _ = client.exec_command(
        f"grep -c install_admin_dashboard {REMOTE_OLD}/server.py 2>/dev/null; "
        f"curl -s -o /dev/null -w '%{{http_code}}' 'http://127.0.0.1:8000/admin/dashboard?window_hours=24'",
        timeout=30,
    )
    print(o.read().decode("utf-8", errors="replace"))


def main() -> int:
    if not PWD:
        print("VPS_PASSWORD not set", file=sys.stderr)
        return 1

    import paramiko

    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    print(f"Connecting to {USER}@{HOST}...")
    client.connect(HOST, username=USER, password=PWD, timeout=30)
    sftp = client.open_sftp()

    for rel in FILES:
        local = os.path.join(REPO, rel.replace("/", os.sep))
        remote = f"{REMOTE}/{rel}"
        remote_dir = os.path.dirname(remote).replace("\\", "/")
        path = ""
        for p in remote_dir.split("/"):
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
        print(f"  upload {rel}")
        sftp.put(local, remote)

    wire_server(sftp, client)
    sftp.close()

    cmd = f"cd {REMOTE}/dashboard && npm run build"
    print(f"\n>>> {cmd}")
    _, stdout, stderr = client.exec_command(cmd, get_pty=True, timeout=600)
    out = stdout.read().decode(errors="replace")
    code = stdout.channel.recv_exit_status()
    print(out[-4000:] if len(out) > 4000 else out)
    if code != 0:
        print(stderr.read().decode(errors="replace")[-2000:], file=sys.stderr)
        client.close()
        return code

    _, o, _ = client.exec_command("pm2 restart telegram-backend 2>/dev/null || true", timeout=60)
    print(o.read().decode("utf-8", errors="replace")[:800])
    client.close()
    print("\nAdmin deploy done.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
