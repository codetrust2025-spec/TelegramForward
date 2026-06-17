import os
import re
import paramiko

PWD = os.environ.get("VPS_PASSWORD", "")
c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect("187.127.169.159", username="root", password=PWD, timeout=30)

cmd = r"""python3 <<'PY'
import pathlib, re
t = pathlib.Path("/opt/telegramforward/dashboard/src/teleautomation-app.jsx").read_text(encoding="utf-8", errors="replace")
for name in ["_Component25", "Pending works", "pending works", "pendingWorks", "works pending"]:
    print("count", name, t.count(name))
m = re.search(r"function _Component25\([^)]*\)", t)
if m:
    i = m.start()
    print(t[i:i+3500].encode("ascii", "replace").decode())
# also search pending near Component25 usage area
idx = t.find("_Component25")
print("\nusage context:")
print(t[idx-200:idx+800].encode("ascii", "replace").decode())
PY"""
_, o, _ = c.exec_command(cmd)
print(o.read().decode("utf-8", "replace"))
c.close()
