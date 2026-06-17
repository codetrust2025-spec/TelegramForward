import os
import paramiko

PWD = os.environ.get("VPS_PASSWORD", "")
c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect("187.127.169.159", username="root", password=PWD, timeout=30)

cmd = r"""python3 <<'PY'
import pathlib, re
js = pathlib.Path("/opt/telegramforward/static/assets/dashboard.bundle.js").read_text(encoding="utf-8", errors="replace")
idx = js.find('id:"daily",label:"Daily ops"')
print("tab idx", idx)
# find daily tab content render
m = re.search(r'o==="daily"[^}]{0,200}', js[idx:idx+50000])
if m:
    print(m.group()[:200])
idx2 = js.find('o==="daily"')
print("render idx", idx2)
if idx2 >= 0:
    print(js[idx2:idx2+4000].encode("ascii","replace").decode())
PY"""
_, o, _ = c.exec_command(cmd)
print(o.read().decode("utf-8", "replace")[:12000])
c.close()
