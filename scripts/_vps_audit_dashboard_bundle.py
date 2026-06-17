import os
import paramiko

PWD = os.environ.get("VPS_PASSWORD", "")
c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect("187.127.169.159", username="root", password=PWD, timeout=30)

cmd = r"""python3 <<'PY'
import pathlib, re
js = pathlib.Path("/opt/telegramforward/static/assets/dashboard.bundle.js").read_text(encoding="utf-8", errors="replace")
checks = [
    "daily-ops", "Daily ops", "Works pending", "PendingWorksProvider",
    "data-room", "Data room", "ta_session", "/auth/login",
    "data-room-creds-fix", "embeddedfolderview", "cand-workspace",
    "PendingWorksContext", "pendingInterviewCount", "kW",
]
for c in checks:
    print(f"{c}: {js.count(c)}")
# main nav views
for m in re.finditer(r'value:"([a-z-]+)".{0,30}label:"([^"]+)"', js):
    v,l = m.groups()
    if v in {"dashboard","inbox","candidates","data-room","admin","logs","daily-ops"} or "daily" in v or "ops" in l.lower():
        print("NAV", v, l)
# find kW component (Daily ops admin tab)
idx = js.find("function kW")
if idx < 0:
    idx = js.find("kW=function")
print("kW idx", idx)
if idx >= 0:
    print(js[idx:idx+2500].encode("ascii","replace").decode()[:2500])
PY"""
_, o, _ = c.exec_command(cmd)
print(o.read().decode("utf-8", "replace")[:12000])
c.close()
