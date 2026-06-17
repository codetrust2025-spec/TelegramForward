import os
import paramiko

PWD = os.environ.get("VPS_PASSWORD", "")
c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect("187.127.169.159", username="root", password=PWD, timeout=30)

cmd = r"""python3 <<'PY'
import pathlib, re
t = pathlib.Path("/opt/telegramforward/dashboard/src/teleautomation-app.jsx").read_text(encoding="utf-8", errors="replace")
# pipeline-related class names
for m in re.finditer(r'className="([a-z-]*pipeline[a-z-]*)"', t):
    print("class", m.group(1))
for m in re.finditer(r'className="([a-z-]*workspace[a-z-]*)"', t):
    if m.group(1) not in ("handler-workspace",):
        print("ws", m.group(1))
# search pending work as two words with anything between
for m in re.finditer(r'.{0,30}[Pp]ending.{0,20}[Ww]ork.{0,30}', t):
    s = m.group()
    if "pendingProps" not in s and "pendingId" not in s and "pending_count" not in s and "pending_only" not in s and "pending_total" not in s and "Pending only" not in s and "Pending collections" not in s and "balance pending" not in s:
        print("MATCH", s.encode("ascii","replace").decode())
PY"""
_, o, _ = c.exec_command(cmd)
print(o.read().decode("utf-8", "replace"))
c.close()
