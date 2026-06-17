import os
import paramiko

PWD = os.environ.get("VPS_PASSWORD", "")
c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect("187.127.169.159", username="root", password=PWD, timeout=30)

cmd = r"""python3 <<'PY'
import pathlib, re
js = pathlib.Path("/opt/telegramforward/static/assets/dashboard.bundle.js").read_text(encoding="utf-8", errors="replace")
for label in ["Daily ops", "daily-ops", "dailyOps", "daily_ops"]:
    idx = js.find(label)
    print(label, "count", js.count(label), "idx", idx)
idx = js.find("Daily ops")
if idx < 0:
    idx = js.find("daily-ops")
if idx >= 0:
    print(js[max(0,idx-600):idx+2000].encode("ascii","replace").decode())
# nav items
for m in re.finditer(r'label:"([^"]{3,40})"', js):
    s = m.group(1)
    if any(k in s.lower() for k in ["daily", "ops", "data", "candid", "admin", "inbox", "dashboard"]):
        pass
nav = sorted(set(re.findall(r'value:"([a-z-]+)".{0,40}label:"([^"]+)"', js)))
print("\nNAV OPTIONS sample:")
for v,l in nav[:30]:
    if any(k in l.lower() or k in v for k in ["daily","ops","data","cand","admin","dash","inbox","log"]):
        print(v, l)
PY"""
_, o, _ = c.exec_command(cmd)
print(o.read().decode("utf-8", "replace")[:10000])
c.close()
