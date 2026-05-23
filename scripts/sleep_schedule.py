"""Print safe restart order from group_intelligence + typical heavy wait."""
from __future__ import annotations

import json
import sys
from datetime import datetime, timedelta
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE))
from core.config import ACCOUNT_SLOTS

DATA = BASE / "data" / "accounts"
DEFAULT_HEAVY_SECS = 15 * 3600 + 39 * 60  # 56340 from recent logs


def main() -> None:
    rows = []
    for slot in ACCOUNT_SLOTS:
        p = DATA / slot / "group_intelligence.json"
        if not p.exists():
            continue
        d = json.loads(p.read_text(encoding="utf-8"))
        acct = d.get("account") or {}
        groups = d.get("groups") or {}
        best_ts = 0.0
        best_name = ""
        for name, g in groups.items():
            if g.get("last_result") != "flood":
                continue
            ts = float(g.get("last_processed") or 0)
            if ts > best_ts:
                best_ts = ts
                best_name = name
        secs = DEFAULT_HEAVY_SECS
        if best_ts:
            wake = datetime.fromtimestamp(best_ts) + timedelta(seconds=secs)
            rows.append(
                {
                    "slot": slot,
                    "health": acct.get("health_score"),
                    "success": acct.get("total_success"),
                    "failure": acct.get("total_failure"),
                    "flood_group": best_name,
                    "flood_at": datetime.fromtimestamp(best_ts),
                    "wake_at": wake,
                    "wait_h": secs / 3600,
                }
            )
        else:
            rows.append(
                {
                    "slot": slot,
                    "health": acct.get("health_score"),
                    "success": acct.get("total_success"),
                    "failure": acct.get("total_failure"),
                    "flood_group": "(disk: no flood row)",
                    "flood_at": None,
                    "wake_at": None,
                    "wait_h": secs / 3600,
                }
            )

    rows_with_wake = [r for r in rows if r["wake_at"]]
    rows_with_wake.sort(key=lambda r: r["wake_at"])

    print("SAFE RESTART SCHEDULE (use dashboard timer if different)\n")
    print(f"Assumed heavy wait: {DEFAULT_HEAVY_SECS // 3600}h {(DEFAULT_HEAVY_SECS % 3600) // 60}m per recent bans\n")
    now = datetime.now()
    print(f"Now (local): {now.strftime('%Y-%m-%d %H:%M:%S')}\n")

    for i, r in enumerate(rows_with_wake, 1):
        left = r["wake_at"] - now
        left_h = max(0, left.total_seconds()) / 3600
        print(f"{i}. {r['slot']}  health={r['health']}  ok={r['success']} fail={r['failure']}")
        print(f"   last flood: {r['flood_group']} @ {r['flood_at'].strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"   start AFTER: {r['wake_at'].strftime('%Y-%m-%d %H:%M:%S')}  (~{left_h:.1f}h from now)")
        print(f"   gap: wait 24h after previous account before starting next\n")

    no_wake = [r for r in rows if not r["wake_at"]]
    if no_wake:
        print("No flood timestamp on disk (use UI sleep timer):")
        for r in no_wake:
            print(f"  - {r['slot']} health={r['health']}")


if __name__ == "__main__":
    main()
