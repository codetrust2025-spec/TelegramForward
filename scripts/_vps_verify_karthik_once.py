import asyncio
from dotenv import load_dotenv
load_dotenv("/opt/telegramforward/.env")
from core.karthik_inbox_sweep import status
from core import ai_smart_reply
print("sweep", status())
print("health", ai_smart_reply.health())
print("catch_up", asyncio.run(ai_smart_reply.catch_up_pending_replies(max_replies=8)))
