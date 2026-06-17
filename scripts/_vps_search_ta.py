import os
import paramiko

PWD = os.environ.get("VPS_PASSWORD", "")
c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect("187.127.169.159", username="root", password=PWD, timeout=30)
path = "/opt/telegramforward/dashboard/src/teleautomation-app.jsx"
patterns = [
    "MESSAGE TO SEND",
    "Posting mode",
    "AccountCard",
    "acct-v3",
    "posting-mode",
    "export default",
    "TeleAutomation",
]
for pat in patterns:
    _, o, _ = c.exec_command(f"grep -n '{pat}' {path} 2>/dev/null | head -5")
    lines = o.read().decode("utf-8", errors="replace").strip()
    print(f"--- {pat} ---")
    print(lines or "(none)")
c.close()
