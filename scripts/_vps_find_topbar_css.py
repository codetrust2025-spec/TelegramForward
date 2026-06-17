import os
import paramiko

PWD = os.environ.get("VPS_PASSWORD", "")
c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect("187.127.169.159", username="root", password=PWD, timeout=30)
cmds = [
    "grep -rn 'cand-page-topbar\\|handler-workspace' /opt/telegramforward/dashboard 2>/dev/null | head -40",
    "grep -rn 'cand-page-topbar\\|handler-workspace' /opt/telegramforward/static 2>/dev/null | head -20",
]
for cmd in cmds:
    print("===", cmd[:70], "===")
    _, o, _ = c.exec_command(cmd)
    print(o.read().decode("utf-8", "replace")[:3000] or "(none)")
c.close()
