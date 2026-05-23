"""
Trace account1/account2 rate-limit history from disk + optional live Telegram probe.
Run: python scripts/trace_account_limits.py
"""
from __future__ import annotations

import asyncio
import json
import os
import sys
from datetime import datetime

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE)

from core.config import ACCOUNTS, STATE_DIR, FLOOD_HARD_BAN_SECONDS


def _load_intel(slot: str) -> dict:
    path = os.path.join(STATE_DIR, slot, "group_intelligence.json")
    if not os.path.exists(path):
        return {}
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def trace_history(slot: str) -> None:
    data = _load_intel(slot)
    acct = data.get("account") or {}
    groups = data.get("groups") or {}

    events = []
    for name, g in groups.items():
        ts = g.get("last_processed")
        res = g.get("last_result") or ""
        if not ts or not res:
            continue
        events.append((float(ts), name, res, g.get("failure", 0)))

    events.sort(key=lambda x: x[0])
    print(f"\n{'=' * 60}\n{slot} — account stats\n{'=' * 60}")
    print(
        f"  health_score={acct.get('health_score')}  "
        f"rate_limits={acct.get('rate_limits')}  "
        f"success={acct.get('total_success')}  failure={acct.get('total_failure')}  "
        f"delay_mult={acct.get('delay_multiplier')}"
    )
    if not events:
        print("  (no processed groups in intelligence file)")
        return

    print(f"\n  Timeline ({len(events)} events):")
    for ts, name, res, fail in events:
        t = datetime.fromtimestamp(ts).strftime("%H:%M:%S")
        mark = "[F]" if res == "flood" else "[OK]" if res in ("sent", "joined_sent", "ok") else "[.]"
        print(f"    {t}  {mark} {res:12}  {name}")

    floods = [e for e in events if e[2] == "flood"]
    sends = [e for e in events if e[2] in ("sent", "joined_sent", "ok")]
    print(f"\n  Summary: {len(sends)} post OK, {len(floods)} flood hits")
    if len(floods) >= 2 and len(sends) <= 2:
        print(
            "  >> PATTERN: Many floods while still cycling — Telegram often escalates "
            "to 15h+ after repeated API use. Stop cycle after 1-2 floods when health is low."
        )


async def live_probe(slot: str) -> None:
    from telethon.errors import FloodWaitError
    from core.config import API_ID, API_HASH
    from telethon import TelegramClient

    session = ACCOUNTS[slot]
    print(f"\n  Live probe ({slot}, session={session})...")
    client = TelegramClient(session, API_ID, API_HASH)
    await client.connect()
    if not await client.is_user_authorized():
        print("    NOT LOGGED IN")
        await client.disconnect()
        return

    probes = [
        ("get_messages(@telegram)", lambda: client.get_messages("telegram", limit=1)),
    ]
  # probe groups from intel floods
    intel = _load_intel(slot)
    for name, g in (intel.get("groups") or {}).items():
        if g.get("last_result") == "flood":
            probes.append(
                (f"get_messages({name})", lambda n=name: client.get_messages(n, limit=1))
            )
            break

    for label, fn in probes:
        try:
            await fn()
            print(f"    OK  {label}")
        except FloodWaitError as e:
            h = e.seconds // 3600
            print(f"    FLOOD  {label}  →  wait {e.seconds}s (~{h}h {e.seconds % 3600 // 60}m)")
            if e.seconds >= FLOOD_HARD_BAN_SECONDS:
                print("           *** HEAVY BAN — do not run worker until this expires")
        except Exception as ex:
            print(f"    ERR   {label}  →  {ex}")
    await client.disconnect()


async def main() -> None:
    for slot in ("account1", "account2"):
        trace_history(slot)
        try:
            await live_probe(slot)
        except Exception as e:
            print(f"    Live probe failed: {e}")


if __name__ == "__main__":
    asyncio.run(main())
