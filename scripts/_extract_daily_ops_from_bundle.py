"""Extract Daily ops (kW) and related snippets from dashboard.bundle.js on VPS."""
import os
import re
import sys

import paramiko

HOST = "187.127.169.159"
PWD = os.environ.get("VPS_PASSWORD", "")
if not PWD:
    print("VPS_PASSWORD required", file=sys.stderr)
    sys.exit(1)

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(HOST, username="root", password=PWD, timeout=30)

cmd = r"""python3 <<'PY'
import pathlib, re

js = pathlib.Path("/opt/telegramforward/static/assets/dashboard.bundle.js").read_text(
    encoding="utf-8", errors="replace"
)

# kW Daily ops admin component
for m in re.finditer(r"function kW\(", js):
    start = m.start()
    print("=== kW component at", start, "===")
    print(js[start : start + 15000])
    break

# PendingWorksProvider
idx = js.find("function PN(")
if idx >= 0:
    print("\n=== PendingWorksProvider (PN) ===")
    print(js[idx : idx + 2500])

# daily-ops nav entry
for pat in [
    'value:"daily-ops"',
    'label:"Daily ops"',
    'mainView==="daily-ops"',
    'e==="daily-ops"',
    'n==="daily-ops"',
]:
    i = js.find(pat)
    print(f"\n=== {pat} at {i} ===")
    if i >= 0:
        print(js[max(0, i - 300) : i + 1200])

# CSS daily-ops from dashboard.bundle.css
css = pathlib.Path("/opt/telegramforward/static/assets/dashboard.bundle.css").read_text(
    encoding="utf-8", errors="replace"
)
for cls in ["daily-ops", ".daily-ops"]:
    i = css.find("daily-ops")
    if i >= 0:
        print("\n=== CSS daily-ops ===")
        print(css[max(0, i - 50) : i + 4000][:4000])
        break
PY"""

_, stdout, stderr = c.exec_command(cmd)
out = stdout.read().decode("utf-8", errors="replace")
err = stderr.read().decode("utf-8", errors="replace")
c.close()

out_path = os.path.join(os.path.dirname(__file__), "_extract_daily_ops_output.txt")
with open(out_path, "w", encoding="utf-8") as f:
    f.write(out)
    if err:
        f.write("\n\nSTDERR:\n" + err)

print(out[:25000])
print(f"\nWrote full output to {out_path}")
