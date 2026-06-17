import os
import paramiko

PWD = os.environ.get("VPS_PASSWORD", "")
c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect("187.127.169.159", username="root", password=PWD, timeout=30)

cmd = r"""python3 <<'PY'
import pathlib, re
js = pathlib.Path("/opt/telegramforward/static/assets/dashboard.bundle.js").read_text(encoding="utf-8", errors="replace")
for label in ["cand-page--compact", "cand-workspace", "cand-page-sticky", "Pending only", "onAnalyticsClick", "cand-stat-card--analytics", "Resume"]:
    print(label, js.count(label))
# extract cand-page--compact return block start
idx = js.find('className:"cand-page cand-page--compact"')
if idx < 0:
    idx = js.find("cand-page--compact")
print("compact idx", idx)
if idx >= 0:
    print(js[max(0,idx-800):idx+3500].encode("ascii","replace").decode())
PY"""
_, o, _ = c.exec_command(cmd)
out = o.read().decode("utf-8", "replace")
print(out[:8000])
c.close()
