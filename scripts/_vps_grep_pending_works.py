import os
import paramiko

PWD = os.environ.get("VPS_PASSWORD", "")
c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect("187.127.169.159", username="root", password=PWD, timeout=30)

cmds = [
    "grep -rni 'pending work' /opt/telegramforward/dashboard/src /opt/telegramforward/static 2>/dev/null | head -30",
    "grep -rni 'Pending works' /opt/telegramforward 2>/dev/null | head -30",
    "grep -o 'Pending [^\"]*' /opt/telegramforward/static/assets/app-*.js 2>/dev/null | sort -u | head -30",
    "grep -o 'dr-tab[^\"]*' /opt/telegramforward/static/assets/app-*.js 2>/dev/null | head -20",
]
for cmd in cmds:
    print("===", cmd[:70], "===")
    _, o, _ = c.exec_command(cmd)
    print(o.read().decode("utf-8", "replace")[:2500])
c.close()
