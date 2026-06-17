"""Deploy candidates stats scope fix (server.py + dashboard bundle)."""
from __future__ import annotations

import os
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HOST = "187.127.169.159"
USER = "root"
REMOTES = ["/opt/telegramforward", "/opt/telegramforward.old"]
PASSWORD = os.environ.get("VPS_PASSWORD", "")


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

    for remote in REMOTES:
        print(f"\n=== {remote} ===")
        sftp.put(os.path.join(repo, "server.py"), f"{remote}/server.py")
        print("  uploaded server.py")
        sftp.put(
            os.path.join(repo, "dashboard", "src", "candidates", "candidatesModule.jsx"),
            f"{remote}/dashboard/src/candidates/candidatesModule.jsx",
        )
        print("  uploaded candidatesModule.jsx")

        def put_tree(local_dir: str, remote_dir: str) -> None:
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
                    put_tree(lp, rp)
                else:
                    sftp.put(lp, rp)

        put_tree(static, f"{remote}/static")
        print("  uploaded static/")

    sftp.close()

    for cmd in [
        "pm2 restart telegram-backend --update-env 2>/dev/null || true",
        "sleep 8",
        "curl -s 'http://127.0.0.1:8000/candidates/stats?month=2026-06&reference=Thrilok' | head -c 400",
        "ls -t /opt/telegramforward.old/static/assets/app-*.js 2>/dev/null | head -1",
        "ls -t /opt/telegramforward/static/assets/app-*.js 2>/dev/null | head -1",
    ]:
        print(f"\n>>> {cmd}")
        _, stdout, stderr = client.exec_command(cmd, timeout=120)
        out = stdout.read().decode(errors="replace")
        err = stderr.read().decode(errors="replace")
        if out:
            print(out[-2000:])
        if err.strip():
            print(err[-500:], file=sys.stderr)

    client.close()
    print("\nStats scope deploy done.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
