import os
import paramiko

PWD = os.environ.get("VPS_PASSWORD", "")
c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect("187.127.169.159", username="root", password=PWD, timeout=30)

cmd = r"""python3 <<'PY'
import pathlib, re
for name in ["dashboard.bundle.js", "dashboard.bundle.css", "index-buYID2R_.js"]:
    p = pathlib.Path("/opt/telegramforward/static/assets") / name
    if p.exists():
        print(name, p.stat().st_size, "mtime", p.stat().st_mtime)
js = pathlib.Path("/opt/telegramforward/static/assets/dashboard.bundle.js").read_text(encoding="utf-8", errors="replace")
for pat in ["BUILD_STAMP", "build", "2026-06"]:
    if pat in js:
        idx = js.find(pat)
        print(pat, js[idx:idx+80].encode("ascii","replace").decode())
# nav items with daily-ops
for m in re.finditer(r'\{value:"([^"]+)",label:"([^"]+)"\}', js):
    v,l = m.group(1), m.group(2)
    if "daily" in v or "ops" in l.lower() or v in ("dashboard","candidates","data-room","admin"):
        print("VIEW", v, "->", l)
PY"""
_, o, _ = c.exec_command(cmd)
print(o.read().decode("utf-8", "replace"))
c.close()
