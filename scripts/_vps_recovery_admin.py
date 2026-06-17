"""Recover backend: fix admin_dashboard import and register /admin/dashboard."""
from __future__ import annotations

import os
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import paramiko

REMOTE = "/opt/telegramforward.old"
PWD = os.environ.get("VPS_PASSWORD", "")


def main() -> int:
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect("187.127.169.159", "root", password=PWD, timeout=30)

    _, o, _ = c.exec_command(
        f"cd {REMOTE} && python3 -c \"from core.admin_dashboard import install_admin_dashboard; print('ok', install_admin_dashboard)\" 2>&1",
        timeout=60,
    )
    imp = o.read().decode("utf-8", errors="replace")
    print("import test:", imp)

    _, o, _ = c.exec_command(f"grep -n '^def ' {REMOTE}/core/admin_dashboard.py | tail -15", timeout=60)
    print("functions:", o.read().decode("utf-8", errors="replace"))

    sftp = c.open_sftp()
    with sftp.open(f"{REMOTE}/core/admin_dashboard.py", "r") as f:
        admin_py = f.read().decode("utf-8")

    with sftp.open(f"{REMOTE}/server.py", "r") as f:
        server = f.read().decode("utf-8")

    # Fix wrong import name if needed
    if "ImportError" in imp or "cannot import" in imp:
        if "def register_admin" in admin_py:
            server = server.replace(
                "from core.admin_dashboard import install_admin_dashboard\ninstall_admin_dashboard(app)",
                "from core.admin_dashboard import register_admin_routes\nregister_admin_routes(app)",
            )
            print("fixed import -> register_admin_routes")
        elif "def setup_admin" in admin_py:
            for name in ("setup_admin", "mount_admin", "add_admin_routes"):
                if f"def {name}" in admin_py:
                    server = server.replace(
                        "install_admin_dashboard",
                        name,
                    )
                    print(f"fixed import -> {name}")
                    break
        else:
            # Add installer at end of admin_dashboard.py
            if "def install_admin_dashboard" not in admin_py:

                def_line = admin_py.rfind("def build_")
                if "def build_admin_dashboard" in admin_py or "def get_admin_dashboard" in admin_py:
                    installer = '''

def install_admin_dashboard(app):
    """Register Admin UI routes."""

    @app.get("/admin/dashboard")
    async def admin_dashboard(window_hours: int = 24):
        try:
            from core.admin_dashboard import build_admin_dashboard
            payload = build_admin_dashboard(window_hours=window_hours)
            return {"status": "ok", **payload}
        except Exception as exc:
            import traceback
            traceback.print_exc()
            return {"status": "error", "message": str(exc)}
'''
                    # try build_admin_dashboard or aggregate function at end of file
                    if "def build_admin_dashboard" not in admin_py:
                        if "def admin_dashboard_data" in admin_py:
                            installer = installer.replace("build_admin_dashboard", "admin_dashboard_data")
                        elif "def get_dashboard" in admin_py:
                            installer = installer.replace("build_admin_dashboard", "get_dashboard")
                    admin_py = admin_py.rstrip() + installer
                    with sftp.open(f"{REMOTE}/core/admin_dashboard.py", "w") as f:
                        f.write(admin_py.encode("utf-8"))
                    print("appended install_admin_dashboard wrapper")
                else:
                    # remove broken server lines
                    server = server.replace(
                        "from core.admin_dashboard import install_admin_dashboard\ninstall_admin_dashboard(app)\n\n",
                        "",
                    )
                    server = server.replace(
                        "from core.admin_dashboard import install_admin_dashboard\ninstall_admin_dashboard(app)\n",
                        "",
                    )
                    print("removed broken install from server.py")

    with sftp.open(f"{REMOTE}/server.py", "w") as f:
        f.write(server.encode("utf-8"))

    sftp.close()

    for cmd in [
        f"cd {REMOTE} && python3 -c \"from core.admin_dashboard import install_admin_dashboard; install_admin_dashboard\" 2>&1",
        "pm2 restart telegram-backend",
        "sleep 10",
        "curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1:8000/health",
        "curl -s -o /dev/null -w '%{http_code}' 'http://127.0.0.1:8000/admin/dashboard?window_hours=24'",
        "pm2 logs telegram-backend --lines 20 --nostream 2>&1 | tail -15",
    ]:
        print(">>>", cmd[:85])
        _, o, _ = c.exec_command(cmd, timeout=120)
        print(o.read().decode("utf-8", errors="replace")[:800])

    c.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
