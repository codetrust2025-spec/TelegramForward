import os
import paramiko

PWD = os.environ.get("VPS_PASSWORD", "")
c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect("187.127.169.159", username="root", password=PWD, timeout=30)
for path in [
    "/opt/telegramforward/dashboard/src/teleautomation.css",
    "/opt/telegramforward/dashboard/src/index.css",
]:
    _, o, _ = c.exec_command(f"grep -n 'crm-inbox-toolbar\\|call-analytics\\|wa-chat-header' {path} 2>/dev/null | head -30", timeout=30)
    out = o.read().decode("utf-8", errors="replace")
    if out.strip():
        print(f"=== {path} ===")
        print(out)
c.close()
