import asyncio
import json
import os
import sys

sys.path.insert(0, "/opt/telegramforward.old")
os.chdir("/opt/telegramforward.old")

from dotenv import load_dotenv

load_dotenv("/opt/telegramforward.old/.env", override=False)


async def run():
    from core import ai_smart_reply
    from core.karthik_inbox_sweep import status as sweep_status, sweep_pending_inbox
    from core.ai_smart_reply_store import get_config
    from core.config import ACCOUNTS
    from core import telegram_client

    cfg = get_config()
    health = ai_smart_reply.health()
    pending = ai_smart_reply.list_pending_inbound_targets()
    sweep = sweep_status()

    out = {
        "accounts": list(ACCOUNTS.keys()),
        "ai_enabled": ai_smart_reply.is_enabled(),
        "mode": cfg.get("mode"),
        "login_exclusive": telegram_client.any_login_exclusive(),
        "health": health,
        "pending_count": len(pending),
        "pending_sample": pending[:10],
        "sweep": sweep,
    }

    try:
        out["sweep_run"] = await sweep_pending_inbox()
    except Exception as e:
        out["sweep_run_error"] = str(e)

    print(json.dumps(out, indent=2, default=str))


asyncio.run(run())
