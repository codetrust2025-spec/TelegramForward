import os
import paramiko

PWD = os.environ.get("VPS_PASSWORD", "")
c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect("187.127.169.159", username="root", password=PWD, timeout=30)

cmd = r"""python3 <<'PY'
import pathlib, re, glob
root = pathlib.Path("/opt/telegramforward/static")
html = (root / "index.html").read_text(encoding="utf-8", errors="replace")
print("index.html refs:", re.findall(r'/assets/[^"\']+', html))
for js in sorted((root / "assets").glob("app-*.js"), key=lambda p: p.stat().st_mtime, reverse=True)[:5]:
    t = js.read_text(encoding="utf-8", errors="replace")
    flags = {k: (k in t) for k in ["cand-workspace", "cand-page-topbar", "handler-workspace", "Pending only", "cand-page--compact"]}
    print(js.name, flags)
for css in sorted((root / "assets").glob("index-*.css"), key=lambda p: p.stat().st_mtime, reverse=True)[:3]:
    t = css.read_text(encoding="utf-8", errors="replace")
    flags = {k: (k in t) for k in ["cand-workspace", "cand-page-topbar", "handler-workspace", "cand-page--compact"]}
    print(css.name, flags)
PY"""
_, o, _ = c.exec_command(cmd)
print(o.read().decode("utf-8", "replace"))
c.close()
