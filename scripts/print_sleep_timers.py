import json
import sys
import urllib.request
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from core.config import ACCOUNT_SLOTS

data = json.loads(urllib.request.urlopen("http://127.0.0.1:8000/state").read())
now = datetime.now()
states = data.get("account_states") or {}
rows = []
for slot in ACCOUNT_SLOTS:
    s = states.get(slot) or {}
    left = int(s.get("next_cycle_in") or 0)
    rows.append(
        (
            left,
            slot,
            s.get("heavy_rate_limit", False),
            s.get("running", False),
            s.get("status", "?"),
            s.get("health_score"),
        )
    )

rows.sort(key=lambda x: x[0] if x[0] else 10**9)
print(f"Now: {now.strftime('%Y-%m-%d %H:%M:%S')}\n")
for left, slot, heavy, running, status, health in rows:
    h, m = left // 3600, (left % 3600) // 60
    wake = now + timedelta(seconds=left + 1800) if left else None
    print(
        f"{slot}: {h}h {m}m left | "
        f"{'RUNNING' if running else 'STOPPED'} | heavy={heavy} | health={health}"
    )
    if wake:
        print(f"  -> Start at/after: {wake.strftime('%Y-%m-%d %H:%M')} (includes 30m buffer)")
    print()
