import os
import paramiko

PWD = os.environ.get("VPS_PASSWORD", "")
c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect("187.127.169.159", username="root", password=PWD, timeout=30)

cmd = r"""python3 <<'PY'
import pathlib, re
js = pathlib.Path("/opt/telegramforward/static/assets/dashboard.bundle.js").read_text(encoding="utf-8", errors="replace")
for pat in ['==="daily"', '==="daily"', 'id:"daily"', 'daily-ops', 'daily_ops', 'DailyOps']:
    print(pat, js.count(pat))
for m in re.finditer(r'.{0,40}==="daily".{0,80}', js):
    print("HIT", m.group().encode("ascii","replace").decode()[:200])
# search daily-ops class
idx = js.find("daily-ops")
print("\ndaily-ops class context:")
print(js[max(0,idx-200):idx+3000].encode("ascii","replace").decode()[:3200])
PY"""
_, o, _ = c.exec_command(cmd)
print(o.read().decode("utf-8", "replace")[:15000])
c.close()
