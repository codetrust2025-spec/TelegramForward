import os
import paramiko

PWD = os.environ.get("VPS_PASSWORD", "")
c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect("187.127.169.159", username="root", password=PWD, timeout=30)
for cmd in [
    "find /opt/telegramforward/dashboard/src -maxdepth 3 -type f -name '*.jsx' 2>/dev/null",
    "find /opt/telegramforward/dashboard/src -maxdepth 3 -type f -name '*cand*' 2>/dev/null",
    "find /opt/telegramforward/dashboard/src -maxdepth 3 -type f -name '*Candidate*' 2>/dev/null",
]:
    _, o, _ = c.exec_command(cmd, timeout=60)
    print("===", cmd, "===")
    print(o.read().decode("utf-8", errors="replace")[:6000] or "(empty)")
c.close()
