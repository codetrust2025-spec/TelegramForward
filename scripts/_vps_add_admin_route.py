"""Add install_admin_dashboard to admin_dashboard.py and wire server."""
import os
import paramiko

PWD = os.environ.get("VPS_PASSWORD", "")
REMOTE = "/opt/telegramforward.old"
INSTALLER = '''

def install_admin_dashboard(app):
    """Register /admin/dashboard for TeleAutomation Admin UI."""

    @app.get("/admin/dashboard")
    async def admin_dashboard_api(window_hours: float = 24):
        try:
            payload = build_dashboard(window_hours=float(window_hours))
            if isinstance(payload, dict) and payload.get("status") == "error":
                return payload
            return {"status": "ok", **(payload if isinstance(payload, dict) else {"data": payload})}
        except Exception as exc:
            return {"status": "error", "message": str(exc)}
'''

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect("187.127.169.159", username="root", password=PWD, timeout=30)
sftp = c.open_sftp()

with sftp.open(f"{REMOTE}/core/admin_dashboard.py", "r") as f:
    admin = f.read().decode("utf-8")

if "def install_admin_dashboard" not in admin:
    admin = admin.rstrip() + INSTALLER
    with sftp.open(f"{REMOTE}/core/admin_dashboard.py", "w") as f:
        f.write(admin.encode("utf-8"))
    print("added install_admin_dashboard")

with sftp.open(f"{REMOTE}/server.py", "r") as f:
    server = f.read().decode("utf-8")

needle = "install_dashboard_auth(app)"
if "install_admin_dashboard" not in server and needle in server:
    server = server.replace(
        needle,
        needle + "\n\nfrom core.admin_dashboard import install_admin_dashboard\ninstall_admin_dashboard(app)",
        1,
    )
    with sftp.open(f"{REMOTE}/server.py", "w") as f:
        f.write(server.encode("utf-8"))
    print("wired server.py")

sftp.close()

for cmd in [
    f"cd {REMOTE} && ./venv/bin/python -c 'from core.admin_dashboard import install_admin_dashboard; print(ok)' 2>&1 || cd /opt/telegramforward && ./venv/bin/python -c 'import sys; sys.path.insert(0,\"/opt/telegramforward.old\"); from core.admin_dashboard import install_admin_dashboard; print(ok)' 2>&1",
    "pm2 restart telegram-backend",
    "sleep 10",
    "curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1:8000/health",
    "curl -s -o /dev/null -w '%{http_code}' 'http://127.0.0.1:8000/admin/dashboard?window_hours=24'",
    "curl -s 'http://127.0.0.1:8000/admin/dashboard?window_hours=24' 2>/dev/null | cut -c1-200",
]:
    print(">>>", cmd[:80])
    _, o, _ = c.exec_command(cmd, timeout=120)
    print(o.read().decode("utf-8", errors="replace")[:600])

c.close()
print("done")
