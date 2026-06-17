import os
import paramiko

PWD = os.environ.get("VPS_PASSWORD", "")
c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect("187.127.169.159", username="root", password=PWD, timeout=30)

cmd = r"""python3 <<'PY'
import pathlib
js = pathlib.Path("/opt/telegramforward/static/assets/app-D89Ign3q.js").read_text(encoding="utf-8", errors="replace")
for label in ["cand-stat-card--analytics", "cand-stat-card--clickable", "onPending", "pending_count", "setPending", "Pending collections"]:
    print(label, js.count(label))
idx = js.find("cand-stat-card--analytics")
if idx >= 0:
    print(js[max(0,idx-600):idx+1000].encode("ascii","replace").decode())
idx = js.find("Pending collections")
print("\nPENDING COLLECTIONS:")
print(js[max(0,idx-500):idx+900].encode("ascii","replace").decode())
PY"""
_, o, _ = c.exec_command(cmd)
print(o.read().decode("utf-8", "replace"))
c.close()
