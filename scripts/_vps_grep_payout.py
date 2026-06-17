import os
import paramiko

PWD = os.environ.get("VPS_PASSWORD", "")
REMOTE = "/opt/telegramforward"
c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect("187.127.169.159", username="root", password=PWD, timeout=30)
patterns = [
    "Edit handler payout",
    "admin password",
    "handler_payout",
    "ADMIN_PASSWORD",
    "payout_password",
    "Method Not Allowed",
    "734720077743",
]
for pat in patterns:
    cmd = f"grep -rn '{pat}' {REMOTE} --include='*.py' --include='*.jsx' --include='*.json' --include='*.env*' 2>/dev/null | head -15"
    _, o, _ = c.exec_command(cmd, timeout=60)
    out = o.read().decode("utf-8", errors="replace").strip()
    print(f"--- {pat} ---")
    print(out or "(none)")
c.close()
