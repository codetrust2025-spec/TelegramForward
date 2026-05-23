"""
Debug Telegram membership scan for one account slot.

Usage:
  python scripts/debug_joined_scan.py account8
  python scripts/debug_joined_scan.py account8 --compare-disk
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE)

from core.account_info_store import load_account_info
from core.config import ACCOUNTS
from core.telegram_client import run_group_operation
from features.telegram_joined_stats import fetch_joined_counts


async def run_scan(slot: str) -> None:
    if slot not in ACCOUNTS:
        print(f"Unknown slot: {slot}")
        sys.exit(1)

    disk = load_account_info(slot) or {}
    print(f"\n=== {slot} disk (account_info.json) ===")
    print(
        f"  joined_total={disk.get('joined_total')} "
        f"groups={disk.get('joined_groups')} channels={disk.get('joined_channels')}"
    )
    print(f"  joined_updated_at={disk.get('joined_updated_at')}")
    print(f"  phone={disk.get('phone')} name={disk.get('name')}")

    print(f"\n=== {slot} live scan ===")

    async def _op(client):
        return await fetch_joined_counts(client)

    stats = await run_group_operation(slot, _op, attempts=3)
    debug = stats.pop("_scan_debug", {})

    print(
        f"  joined_total={stats['joined_total']} "
        f"groups={stats['joined_groups']} channels={stats['joined_channels']}"
    )
    print(f"  joined_updated_at={stats['joined_updated_at']}")
    print(f"\n  scan debug:")
    print(json.dumps(debug, indent=4))

    if disk.get("joined_total") is not None:
        delta = int(stats["joined_total"]) - int(disk.get("joined_total") or 0)
        if delta:
            print(f"\n  MISMATCH vs disk: live scan differs by {delta:+d}")
        else:
            print("\n  Matches disk joined_total.")


def main() -> None:
    parser = argparse.ArgumentParser(description="Debug joined dialog scan")
    parser.add_argument("slot", help="Account slot, e.g. account8")
    args = parser.parse_args()
    asyncio.run(run_scan(args.slot))


if __name__ == "__main__":
    main()
