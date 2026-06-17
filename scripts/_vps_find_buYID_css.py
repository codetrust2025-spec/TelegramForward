import os
import paramiko

PWD = os.environ.get("VPS_PASSWORD", "")
c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect("187.127.169.159", username="root", password=PWD, timeout=30)
cmds = [
    "grep -rni buYID2R /opt/telegramforward/static 2>/dev/null | head -10",
    "grep -rni 'index-buYID2R' /opt/telegramforward 2>/dev/null | head -10",
    "ls -la /opt/telegramforward/static/assets/index-buYID2R* 2>/dev/null",
    "ls -la /opt/telegramforward/static/assets/dashboard.bundle.css",
]
for cmd in cmds:
    print("===", cmd)
    _, o, _ = c.exec_command(cmd)
    print(o.read().decode("utf-8", "replace")[:2000])
c.close()
