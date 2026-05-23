"""
Track one account: disk stats + live Telethon health probe.

Usage:
  python scripts/track_account.py account4
"""
from __future__ import annotations

import asyncio
import json
import os
import sys
from datetime import datetime

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE)

from core.config import ACCOUNTS, API_ID, API_HASH, STATE_DIR
from telethon import TelegramClient
from telethon.errors import FloodWaitError


def load_intel(slot: str) -> dict:
    path = os.path.join(STATE_DIR, slot, "group_intelligence.json")
    if not os.path.exists(path):
        return {}
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def print_disk(slot: str) -> None:
    data = load_intel(slot)
    acct = data.get("account") or {}
    groups = data.get("groups") or {}
    floods = [
        (g.get("last_processed"), name)
        for name, g in groups.items()
        if isinstance(g, dict) and g.get("last_result") == "flood"
    ]
    floods = [(t, n) for t, n in floods if t]
    floods.sort(reverse=True)
    print(f"\n=== {slot} (disk) ===")
    print(
        f"  health={acct.get('health_score')}  ok={acct.get('total_success')}  "
        f"fail={acct.get('total_failure')}  rate_limits={acct.get('rate_limits')}"
    )
    if floods:
        ts, name = floods[0]
        print(f"  last_flood: {name} @ {datetime.fromtimestamp(ts)}")
    running = os.path.join(BASE, "data", ".running_workers.json")
    if os.path.exists(running):
        with open(running, encoding="utf-8") as f:
            slots = json.load(f)
        print(f"  persisted_running: {slot in slots}")


async def live_probe(slot: str) -> None:
    session = ACCOUNTS[slot]
    print(f"\n=== {slot} (live probe) ===")
    print(f"  session: {session}.session")
    client = TelegramClient(session, API_ID, API_HASH)
    try:
        await client.connect()
        print(f"  connected: {client.is_connected()}")
        auth = await client.is_user_authorized()
        print(f"  authorized: {auth}")
        if auth:
            me = await client.get_me()
            print(f"  user: {me.first_name} (+{me.phone})")
            try:
                await client.get_me()
                print("  health (get_me): OK")
            except FloodWaitError as e:
                print(f"  health: FLOOD {e.seconds}s")
            except Exception as e:
                print(f"  health: FAIL {type(e).__name__}: {e}")
    except Exception as e:
        print(f"  connect: FAIL {type(e).__name__}: {e}")
    finally:
        await client.disconnect()


async def api_state(slot: str) -> None:
    try:
        import urllib.request

        raw = urllib.request.urlopen("http://127.0.0.1:8000/state", timeout=3).read()
        data = json.loads(raw)
        st = (data.get("account_states") or {}).get(slot) or {}
        print(f"\n=== {slot} (dashboard API) ===")
        print(
            f"  running={st.get('running')}  status={st.get('status')}  "
            f"health={st.get('health_score')}  cycle={st.get('cycle')}"
        )
        print(f"  notification: {st.get('notification', '')[:80]}")
    except Exception as e:
        print(f"\n=== {slot} (dashboard API) === unavailable: {e}")


async def main() -> None:
    slot = (sys.argv[1] if len(sys.argv) > 1 else "account4").strip()
    if slot not in ACCOUNTS:
        print(f"Unknown slot {slot}. Valid: {', '.join(ACCOUNTS)}")
        sys.exit(1)
    print_disk(slot)
    await api_state(slot)
    await live_probe(slot)


if __name__ == "__main__":
    asyncio.run(main())
