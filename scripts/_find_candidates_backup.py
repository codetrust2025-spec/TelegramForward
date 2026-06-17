import os
import paramiko

PWD = os.environ["VPS_PASSWORD"]
c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect("187.127.169.159", username="root", password=PWD, timeout=30)
_, o, _ = c.exec_command(
    "find /opt /root -name 'candidates.json' 2>/dev/null | while read f; do "
    "echo $(stat -c '%s' \"$f\") $f; done | sort -rn | head -20"
)
print(o.read().decode("utf-8", errors="replace"))
c.close()
