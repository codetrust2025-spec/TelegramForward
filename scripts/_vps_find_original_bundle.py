import os
import paramiko

PWD = os.environ.get("VPS_PASSWORD", "")
c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect("187.127.169.159", username="root", password=PWD, timeout=30)

cmd = r"""python3 <<'PY'
import pathlib
for root in ["/opt/telegramforward", "/opt/telegramforward.old"]:
    p = pathlib.Path(root)
    if not p.exists():
        continue
    for f in p.rglob("dashboard.bundle.js"):
        t = f.read_text(encoding="utf-8", errors="replace")
        print(f, f.stat().st_size, "import.meta", "import.meta" in t, "Daily ops", "Daily ops" in t, "Works pending", "Works pending" in t)
PY"""
_, o, _ = c.exec_command(cmd)
print(o.read().decode("utf-8", "replace"))
c.close()
