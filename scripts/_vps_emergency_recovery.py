import os
import paramiko

PWD = os.environ.get("VPS_PASSWORD", "")
REMOTE = "/opt/telegramforward.old"
c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect("187.127.169.159", username="root", password=PWD, timeout=30)

cmds = [
    f"cd {REMOTE} && python3 -c 'from core.admin_dashboard import install_admin_dashboard' 2>&1",
    f"grep -n '^def ' {REMOTE}/core/admin_dashboard.py",
    "pm2 logs telegram-backend --lines 25 --nostream 2>&1",
    f"sed -n '54,62p' {REMOTE}/server.py",
]
for cmd in cmds:
    print("===", cmd[:95])
    _, o, _ = c.exec_command(cmd, timeout=90)
    print(o.read().decode("utf-8", errors="replace")[:4000])

# If import fails, remove install lines
_, o, _ = c.exec_command(
    f"cd {REMOTE} && python3 -c 'from core.admin_dashboard import install_admin_dashboard' 2>&1",
    timeout=30,
)
err = o.read().decode()
if "Error" in err or "Traceback" in err:
    print("=== REMOVING broken install ===")
    fix = (
        f"sed -i '/from core.admin_dashboard import install_admin_dashboard/d' {REMOTE}/server.py && "
        f"sed -i '/^install_admin_dashboard(app)/d' {REMOTE}/server.py"
    )
    _, o, _ = c.exec_command(fix, timeout=30)
    print(o.read().decode())
    # append installer to admin_dashboard if build function exists
    _, o, _ = c.exec_command(f"grep -n 'def build_admin\\|def admin_dashboard\\|def get_admin' {REMOTE}/core/admin_dashboard.py", timeout=30)
    print("builders:", o.read().decode())

_, o, _ = c.exec_command("pm2 restart telegram-backend && sleep 10 && curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1:8000/health", timeout=120)
print("health:", o.read().decode())
c.close()
