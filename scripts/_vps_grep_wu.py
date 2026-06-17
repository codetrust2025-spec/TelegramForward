import os, sys, paramiko
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
REMOTE = "/opt/telegramforward"
c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect("187.127.169.159", "root", password=os.environ.get("VPS_PASSWORD", ""), timeout=30)
cmds = [
    f"grep -n 'wu()' {REMOTE}/dashboard/src/teleautomation-app.jsx",
    f"grep -n 'auth-screen' {REMOTE}/dashboard/src/teleautomation.css | head -15",
    f"grep -n 'Rs ' {REMOTE}/dashboard/src/teleautomation-app.jsx | head -5",
    f"wc -c {REMOTE}/static/assets/index-D1YMOX_o.js",
]
for cmd in cmds:
    print("===", cmd)
    _, o, _ = c.exec_command(cmd, timeout=60)
    print(o.read().decode("utf-8", errors="replace")[:3000])
c.close()
