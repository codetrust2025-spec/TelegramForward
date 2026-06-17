import os
import paramiko

PWD = os.environ.get("VPS_PASSWORD", "")
path = "/opt/telegramforward/dashboard/src/teleautomation-app.jsx"
c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect("187.127.169.159", username="root", password=PWD, timeout=30)
for pat in ["posting_modes", "posting_mode", "AccountPanel", "_Component7", "customMessage={"]:
    _, o, _ = c.exec_command(f"grep -n '{pat}' {path} 2>/dev/null | head -8")
    print(f"--- {pat} ---")
    print(o.read().decode("utf-8", errors="replace")[:2500] or "(none)")
c.close()
