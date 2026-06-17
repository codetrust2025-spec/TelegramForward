import os
import paramiko

PWD = os.environ.get("VPS_PASSWORD", "")
c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect("187.127.169.159", username="root", password=PWD, timeout=30)
cmds = [
    "grep -rn 'install_voice\\|voice_api\\|voice/analytics' /opt/telegramforward.old /opt/telegramforward 2>/dev/null | head -40",
    "cat /opt/telegramforward.old/scripts/_remote_voice_diag.py 2>/dev/null | head -80",
    "grep -rn 'calls/start' /opt/telegramforward.old --include='*.py' 2>/dev/null",
]
for cmd in cmds:
    print(">>>", cmd[:90])
    _, o, _ = c.exec_command(cmd, timeout=60)
    print(o.read().decode("utf-8", errors="replace")[:3000])
c.close()
