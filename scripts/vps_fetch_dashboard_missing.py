#!/usr/bin/env python3
import os, socket, sys
from pathlib import Path
import paramiko

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
PASSWORD = os.environ.get("VPS_PASSWORD", "")
REMOTE = "/opt/telegramforward.old/dashboard/src"
LOCAL = Path(r"C:\Users\codet\OneDrive\Desktop\Automation\dashboard\src")
FILES = [
    "desktop/DesktopDashboardHome.jsx",
    "desktop/DesktopHeader.jsx",
    "desktop/DesktopSidebar.jsx",
    "desktop/desktopDashboard.css",
    "dashboard/dashboardStats.js",
    "utils/sabAccountsUi.js",
    "components/ui/ResponsiveOptions.jsx",
    "utils/workspaceMode.js",
    "utils/statsResetConfirm.js",
    "components/SetupMainPanel.jsx",
    "components/FleetDefaultsPanel.jsx",
    "components/ShutdownListPanel.jsx",
    "components/SetupAccountPicker.jsx",
    "mobile/mobileUtils.js",
]

sock = socket.create_connection(("187.127.169.159", 22), timeout=30)
c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect("187.127.169.159", "root", PASSWORD, sock=sock)
sftp = c.open_sftp()
for rel in FILES:
    remote = f"{REMOTE}/{rel}"
    local = LOCAL / rel
    local.parent.mkdir(parents=True, exist_ok=True)
    try:
        sftp.get(remote, str(local))
        print(f"OK {rel} ({local.stat().st_size} bytes)")
    except Exception as e:
        print(f"MISSING {rel}: {e}")
sftp.close()
_, stdout, _ = c.exec_command(f"ls -la {REMOTE}/desktop/ {REMOTE}/dashboard/ 2>&1", timeout=30)
print(stdout.read().decode())
c.close()
