import os
import paramiko

PWD = os.environ.get("VPS_PASSWORD", "")
c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect("187.127.169.159", username="root", password=PWD, timeout=30)

cmd = r"""python3 <<'PY'
import pathlib, re
t = pathlib.Path("/opt/telegramforward/dashboard/src/teleautomation-app.jsx").read_text(encoding="utf-8", errors="replace")
# find sections with __tag">#
for m in re.finditer(r'__tag">(#[0-9]+)</span><h3 className="([^"]+)">([^<]+)</h3>', t):
    print(m.group(1), m.group(2), m.group(3))
# find cand-page children components near CandidatesPanel return
idx = t.find("function _Component35")
chunk = t[idx:idx+8000]
for name in re.findall(r"<(_Component\d+)", chunk):
    pass
comps = re.findall(r"<(_Component\d+)[^>]*>", chunk)
print("comps in panel:", sorted(set(comps)))
PY"""
_, o, _ = c.exec_command(cmd)
print(o.read().decode("utf-8", "replace"))
c.close()
