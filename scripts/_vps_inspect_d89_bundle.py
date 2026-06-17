import os
import paramiko

PWD = os.environ.get("VPS_PASSWORD", "")
c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect("187.127.169.159", username="root", password=PWD, timeout=30)

cmd = r"""python3 <<'PY'
import pathlib
js = pathlib.Path("/opt/telegramforward/static/assets/app-D89Ign3q.js").read_text(encoding="utf-8", errors="replace")
for label in ["cand-workspace", "cand-page-topbar", "handler-workspace", "Pending only", "Pending works", "pending works", "cand-page--compact", "Pending collections"]:
    i = js.find(label)
    print(label, i, js.count(label))
idx = js.find("cand-workspace")
if idx >= 0:
    print(js[max(0,idx-400):idx+1500].encode("ascii","replace").decode())
idx = js.find("cand-page-topbar")
if idx >= 0:
    print("\nTOPBAR:")
    print(js[max(0,idx-200):idx+1200].encode("ascii","replace").decode())
PY"""
_, o, _ = c.exec_command(cmd)
print(o.read().decode("utf-8", "replace"))
c.close()
