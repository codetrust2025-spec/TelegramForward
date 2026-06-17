import asyncio, os, sys
sys.path.insert(0, "/opt/telegramforward.old")
os.chdir("/opt/telegramforward.old")

from services import dm_inbox_service

async def test(slot, uid, mid):
    print("---", slot, uid, mid)
    hit = await dm_inbox_service.ensure_inbox_media_file(slot, uid, mid)
    print("result", hit)

asyncio.run(test("account7", 8345253416, 6333))
asyncio.run(test("account7", 8345253416, 6322))
