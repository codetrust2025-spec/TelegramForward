import os
import paramiko

PWD = os.environ.get("VPS_PASSWORD", "")
c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect("187.127.169.159", username="root", password=PWD, timeout=30)

cmd = r"""python3 <<'PY'
import pathlib, re
t = pathlib.Path("/opt/telegramforward/dashboard/src/teleautomation-app.jsx").read_text(encoding="utf-8", errors="replace")
for label in ["cand-workspace", "cand-page--compact", "cand-page-topbar", "pending works", "Pending works", "cand-workspace__"]:
    print(label, t.count(label))
idx = t.find("cand-workspace")
if idx >= 0:
    print(t[max(0,idx-500):idx+2000].encode("ascii","replace").decode())
PY"""
_, o, _ = c.exec_command(cmd)
print(o.read().decode("utf-8", "replace"))
c.close()
