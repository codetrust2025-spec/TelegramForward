import os
import paramiko

PWD = os.environ.get("VPS_PASSWORD", "")
c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect("187.127.169.159", username="root", password=PWD, timeout=30)

cmd = r"""python3 <<'PY'
import pathlib
t = pathlib.Path("/opt/telegramforward/dashboard/src/teleautomation-app.jsx").read_text(encoding="utf-8", errors="replace")
for label in ["Pending collections", "Pending only", "onPending", "pendingClick", "Pending works", "cand-stat-card--collections"]:
    i = t.find(label)
    print(f"\n=== {label} @ {i} ===")
    if i >= 0:
        print(t[max(0,i-350):i+550].encode("ascii", "replace").decode())
PY"""
_, o, e = c.exec_command(cmd)
print(o.read().decode("utf-8", "replace"))
err = e.read().decode("utf-8", "replace")
if err:
    print("ERR", err)
c.close()
