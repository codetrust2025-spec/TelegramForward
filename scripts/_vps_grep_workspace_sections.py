import os
import paramiko

PWD = os.environ.get("VPS_PASSWORD", "")
c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect("187.127.169.159", username="root", password=PWD, timeout=30)

cmd = r"""python3 <<'PY'
import pathlib, re
t = pathlib.Path("/opt/telegramforward/dashboard/src/teleautomation-app.jsx").read_text(encoding="utf-8", errors="replace")
for pat in [r"handler-workspace", r"pipeline", r"Pending", r"works", r"#1", r"workspace__tag"]:
    print(pat, len(re.findall(pat, t, re.I)))
# find all workspace__tag sections
for m in re.finditer(r'className="handler-workspace__tag">([^<]+)', t):
    start = max(0, m.start()-100)
    print("TAG", m.group(1), "->", t[start:m.start()+200].encode("ascii","replace").decode()[:250])
PY"""
_, o, _ = c.exec_command(cmd)
print(o.read().decode("utf-8", "replace"))
c.close()
