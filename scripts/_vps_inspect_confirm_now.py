import os
import paramiko

PWD = os.environ.get("VPS_PASSWORD", "")
REMOTE = "/opt/telegramforward"
c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect("187.127.169.159", username="root", password=PWD, timeout=30)
cmds = [
    f"cat {REMOTE}/dashboard/src/main.jsx",
    f"grep -n 'ConfirmProvider\\|TeleAutomationApp\\|export default' {REMOTE}/dashboard/src/teleautomation-app.jsx | tail -15",
    f"grep -o 'assets/[^\"]*\\.js' {REMOTE}/static/index.html",
    f"grep -o 'function eo()' {REMOTE}/static/assets/app-*.js | head -1",
    f"grep -o '.__TA_CONFIRM_VALUE__' {REMOTE}/static/assets/app-*.js | head -1 || echo NO_GLOBAL",
]
for cmd in cmds:
    print(">>>", cmd[:100])
    _, o, _ = c.exec_command(cmd, timeout=60)
    print(o.read().decode("utf-8", errors="replace")[:2000])
c.close()
