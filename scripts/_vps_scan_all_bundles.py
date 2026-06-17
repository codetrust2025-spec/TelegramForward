import os
import paramiko

PWD = os.environ.get("VPS_PASSWORD", "")
c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect("187.127.169.159", username="root", password=PWD, timeout=30)

cmd = r"""python3 <<'PY'
import pathlib
p = pathlib.Path("/opt/telegramforward/static/assets")
for f in sorted(p.glob("*.js"), key=lambda x: -x.stat().st_size):
    if f.stat().st_size < 500000:
        continue
    try:
        t = f.read_text(encoding="utf-8", errors="replace")
    except Exception:
        continue
    im = "import.meta" in t
    daily = "Daily ops" in t
    works = "Works pending" in t
    if f.stat().st_size > 1000000:
        print(f"{f.name:40} {f.stat().st_size:>10}  import.meta={im}  Daily ops={daily}  Works pending={works}")
PY"""
_, o, _ = c.exec_command(cmd)
print(o.read().decode("utf-8", "replace"))
c.close()
