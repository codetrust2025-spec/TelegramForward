#!/usr/bin/env python3
"""Set Telegram profile + dashboard display_name for logged-in accounts."""
import asyncio
import sys

from telethon.tl.functions.account import UpdateProfileRequest

from core.account_info_store import build_info_from_me, load_account_info, save_account_info
from core import telegram_client

# Interview-support profile names (dashboard display_name max 48 chars)
PROFILE_NAMES = {
    "account1": "Data Analyst & BI Interview Support",
    "account2": "Interview Support Hub | India",
    "account3": "React JS Interview Support | Frontend",
    "account4": "Interview Clearance Support",
    "account5": "MERN Stack Interview Support",
    "account6": "Power BI Interview Support | Data Analyst",
    "account7": "Power BI · React · MERN | Interview Support",
    "account8": "Real-Time Interview Support",
    "account9": "Interview Support — Calls to Offer",
    "account10": "Live Interview Support | Resume to Offer",
    "account11": "100+ Placed | Interview Support",
}


async def update_slot(slot: str, profile_name: str) -> None:
    info = load_account_info(slot)
    if not info or not info.get("phone"):
        print(f"SKIP {slot}: not logged in")
        return

    label = profile_name.strip()[:48]
    first = label[:64]
    last = ""

    async def op(client):
        await client(UpdateProfileRequest(first_name=first, last_name=last))
        return await client.get_me()

    me = await telegram_client.run_dm_operation(
        slot, op, attach_inbox_handlers=False,
    )
    cached = {**info, "display_name": label}
    new_info = build_info_from_me(me, cached)
    new_info["display_name"] = label
    save_account_info(slot, new_info)
    print(f"OK {slot}: {label} (tg={new_info.get('first_name')})")


async def main() -> None:
    for slot, name in PROFILE_NAMES.items():
        try:
            await update_slot(slot, name)
        except Exception as e:
            print(f"FAIL {slot}: {e}", file=sys.stderr)
        await asyncio.sleep(2.5)


if __name__ == "__main__":
    asyncio.run(main())
