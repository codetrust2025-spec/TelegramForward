"""Wire admin_dashboard routes into running server.py on VPS."""
from __future__ import annotations

import os
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import paramiko

HOST, USER, REMOTE = "187.127.169.159", "root", "/opt/telegramforward.old"
PWD = os.environ.get("VPS_PASSWORD", "")

INSTALL_LINE = "from core.admin_dashboard import install_admin_dashboard\ninstall_admin_dashboard(app)\n"
NEEDLE = "install_dashboard_auth(app)"


def main() -> int:
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(HOST, username=USER, password=PWD, timeout=30)

    _, o, _ = c.exec_command(
        f"grep -n 'install_admin_dashboard\\|/admin/dashboard\\|def install' "
        f"{REMOTE}/server.py {REMOTE}/core/admin_dashboard.py | head -30",
        timeout=60,
    )
    print(o.read().decode("utf-8", errors="replace"))

    _, o, _ = c.exec_command(f"head -40 {REMOTE}/core/admin_dashboard.py", timeout=60)
    print("--- admin_dashboard head ---")
    print(o.read().decode("utf-8", errors="replace"))

    sftp = c.open_sftp()
    with sftp.open(f"{REMOTE}/server.py", "r") as f:
        server = f.read().decode("utf-8")

    changed = False
    if "install_admin_dashboard" not in server:
        if NEEDLE in server:
            server = server.replace(
                NEEDLE,
                NEEDLE + "\n\n" + INSTALL_LINE.rstrip(),
                1,
            )
            changed = True
            print("Added install_admin_dashboard after install_dashboard_auth")
        elif "app = FastAPI()" in server:
            # fallback: after CORS
            cors = 'app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])'
            if cors in server:
                server = server.replace(
                    cors,
                    cors + "\n\n" + INSTALL_LINE.rstrip(),
                    1,
                )
                changed = True
                print("Added install_admin_dashboard after CORS")
        else:
            print("ERROR: could not find insertion point in server.py", file=sys.stderr)
            sftp.close()
            c.close()
            return 1
    else:
        print("install_admin_dashboard already present")

    if changed:
        with sftp.open(f"{REMOTE}/server.py", "w") as f:
            f.write(server.encode("utf-8"))

    sftp.close()

    for cmd in [
        "pm2 restart telegram-backend",
        "sleep 8",
        "pm2 logs telegram-backend --lines 30 --nostream 2>&1 | tail -25",
        "curl -s -o /dev/null -w '%{http_code}' 'http://127.0.0.1:8000/admin/dashboard?window_hours=24'",
        "curl -s 'http://127.0.0.1:8000/admin/dashboard?window_hours=24' | head -c 400",
    ]:
        print(">>>", cmd)
        _, o, _ = c.exec_command(cmd, timeout=90)
        print(o.read().decode("utf-8", errors="replace")[:500])

    c.close()
    print("Done — refresh Admin Overview in browser")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
