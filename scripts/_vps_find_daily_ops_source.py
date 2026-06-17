"""Locate Daily ops source on VPS."""
import os
import sys

import paramiko

PWD = os.environ.get("VPS_PASSWORD", "")
if not PWD:
    print("VPS_PASSWORD required", file=sys.stderr)
    sys.exit(1)

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect("187.127.169.159", username="root", password=PWD, timeout=30)

cmd = r"""python3 <<'PY'
import pathlib, re

patterns = [
    "Daily ops", "daily-ops", "Today's interview roster",
    "PendingWorksProvider", "ops-checklist", "ops-dash-roster",
    "function kW(", "function _W(", "InterviewRoster",
]

for rel in [
    "dashboard/src/teleautomation-app.jsx",
    "scripts/_vps_extract/teleautomation-app.jsx",
]:
    p = pathlib.Path("/opt/telegramforward") / rel
    if not p.exists():
        print(rel, "MISSING")
        continue
    t = p.read_text(encoding="utf-8", errors="replace")
    print(f"\n{rel}: {len(t)} chars, {t.count(chr(10))} lines")
    for pat in patterns:
        idx = t.find(pat)
        print(f"  {pat!r}: {idx if idx >= 0 else 'MISSING'}")

# grep dashboard/src for daily ops jsx files
root = pathlib.Path("/opt/telegramforward/dashboard/src")
for p in sorted(root.rglob("*")):
    if p.suffix not in {".jsx", ".js", ".css"}:
        continue
    try:
        t = p.read_text(encoding="utf-8", errors="replace")
    except Exception:
        continue
    if any(x in t for x in ("Daily ops", "daily-ops", "ops-checklist", "PendingWorksProvider")):
        hits = [x for x in patterns if x in t]
        print("HIT", p.relative_to(root), hits)
PY"""

_, stdout, stderr = c.exec_command(cmd)
print(stdout.read().decode("utf-8", errors="replace"))
err = stderr.read().decode("utf-8", errors="replace")
if err:
    print("STDERR:", err)
c.close()
