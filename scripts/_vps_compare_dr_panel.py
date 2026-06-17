import os
import paramiko

PWD = os.environ.get("VPS_PASSWORD", "")
c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect("187.127.169.159", username="root", password=PWD, timeout=30)

paths = [
    "/opt/telegramforward.old/dashboard/src/components/DataRoomPanel.jsx",
    "/opt/telegramforward/dashboard/src/components/DataRoomPanel.jsx",
]
for p in paths:
    print("===", p, "===")
    _, o, _ = c.exec_command(f"grep -n 'label\\|tab\\|pending\\|work\\|Vault\\|Logins' {p} | head -40")
    print(o.read().decode("utf-8", "replace")[:3000])
c.close()
