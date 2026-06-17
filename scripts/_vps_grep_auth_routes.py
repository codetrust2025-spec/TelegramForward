import os
import paramiko

PWD = os.environ.get("VPS_PASSWORD", "")
c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect("187.127.169.159", username="root", password=PWD, timeout=30)
_, o, _ = c.exec_command(
    "grep -rn '@app\\..*\"/auth' /opt/telegramforward --include='*.py' 2>/dev/null | grep -v venv"
)
print(o.read().decode() or "(none)")
_, o, _ = c.exec_command("grep -rn 'verify.admin\\|verify_admin' /opt/telegramforward --include='*.py' 2>/dev/null | grep -v venv")
print("verify:", o.read().decode() or "(none)")
_, o, _ = c.exec_command("wc -l /opt/telegramforward/server.py; tail -80 /opt/telegramforward/server.py")
print(o.read().decode()[-3000:])
c.close()
