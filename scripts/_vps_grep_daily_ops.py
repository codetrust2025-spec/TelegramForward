import os
import paramiko

PWD = os.environ.get("VPS_PASSWORD", "")
c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect("187.127.169.159", username="root", password=PWD, timeout=30)

cmd = r"""python3 <<'PY'
import pathlib, re
patterns = ["daily ops", "Daily ops", "daily-ops", "dailyOps", "Daily Ops", "Works pending", "cand-workspace", "handler-workspace"]
roots = [
    pathlib.Path("/opt/telegramforward/static/assets"),
    pathlib.Path("/opt/telegramforward/dashboard/src"),
]
for root in roots:
    for p in root.rglob("*"):
        if p.suffix not in {".js", ".jsx", ".css", ".html"}:
            continue
        try:
            t = p.read_text(encoding="utf-8", errors="replace")
        except Exception:
            continue
        hits = [pat for pat in patterns if pat.lower() in t.lower() or pat in t]
        if hits:
            print(p.relative_to(pathlib.Path("/opt/telegramforward")), hits[:6])
# index.html active bundle
html = pathlib.Path("/opt/telegramforward/static/index.html").read_text(encoding="utf-8")
print("ACTIVE", re.findall(r'/assets/[^"\']+', html))
PY"""
_, o, _ = c.exec_command(cmd)
print(o.read().decode("utf-8", "replace")[:8000])
c.close()
