"""Fetch VPS main.jsx and teleautomation root render."""
import os
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
import paramiko

HOST, USER, PWD = "187.127.169.159", "root", os.environ.get("VPS_PASSWORD", "")
REMOTE = "/opt/telegramforward"

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(HOST, username=USER, password=PWD, timeout=30)

for cmd in [
    f"cat {REMOTE}/dashboard/src/main.jsx",
    f"tail -80 {REMOTE}/dashboard/src/teleautomation-app.jsx",
    f"grep -n 'createRoot\\|AuthProvider\\|_Component46\\|PostingModePanel\\|useAuth' {REMOTE}/dashboard/src/main.jsx {REMOTE}/dashboard/src/teleautomation-app.jsx | tail -40",
    f"head -30 {REMOTE}/static/index.html",
    f"grep -o 'useAuth must be used' {REMOTE}/static/assets/index-nAeP5_j5.js | head -1",
    f"grep -n 'createRoot' {REMOTE}/dashboard/src/teleautomation-app.jsx | tail -5",
]:
    print("===", cmd[:90])
    _, o, e = c.exec_command(cmd, timeout=60)
    print(o.read().decode("utf-8", errors="replace")[:8000])
    err = e.read().decode()
    if err:
        print("ERR:", err[:200])
c.close()
