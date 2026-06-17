import os
import paramiko

PWD = os.environ.get("VPS_PASSWORD", "")
c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect("187.127.169.159", username="root", password=PWD, timeout=30)

cmd = r"""python3 <<'PY'
import pathlib, re
assets = pathlib.Path("/opt/telegramforward/static/assets")
for css in assets.glob("index-*.css"):
    t = css.read_text(encoding="utf-8", errors="replace")
    if "cand-workspace" in t:
        print("CSS with cand-workspace:", css.name, "size", css.stat().st_size)
for js in assets.glob("app-*.js"):
    t = js.read_text(encoding="utf-8", errors="replace")
    if "cand-workspace" in t or "cand-page-topbar" in t:
        print("JS match:", js.name, {"workspace": "cand-workspace" in t, "topbar": "cand-page-topbar" in t})
# grep dashboard src for cand-workspace
src = pathlib.Path("/opt/telegramforward/dashboard/src")
for p in src.rglob("*"):
    if p.suffix in {".jsx", ".js", ".css"} and p.is_file():
        try:
            t = p.read_text(encoding="utf-8", errors="replace")
        except Exception:
            continue
        if "cand-workspace" in t:
            print("SRC", p, "count", t.count("cand-workspace"))
PY"""
_, o, _ = c.exec_command(cmd)
print(o.read().decode("utf-8", "replace"))
c.close()
