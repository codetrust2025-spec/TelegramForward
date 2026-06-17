import asyncio, glob, json, os, sys
sys.path.insert(0, "/opt/telegramforward.old")
os.chdir("/opt/telegramforward.old")

def find_denver():
    for path in glob.glob("/opt/telegramforward.old/data/accounts/*/dm_inbox.json"):
        slot = path.split("/")[-2]
        data = json.load(open(path, encoding="utf-8"))
        for uid, conv in (data.get("conversations") or {}).items():
            name = (conv.get("name") or "").lower()
            uname = (conv.get("username") or "").lower()
            if "denver" in name or "denver" in uname:
                msgs = conv.get("messages") or []
                stickers = [
                    m
                    for m in msgs
                    if m.get("media_type") == "sticker"
                    or (m.get("text") or "").strip().lower() == "[sticker]"
                ]
                print("SLOT", slot, "uid", uid, "name", conv.get("name"))
                for m in stickers[:5]:
                    print(
                        " STICKER",
                        {k: m.get(k) for k in ("id", "direction", "text", "media", "media_type", "timestamp")},
                    )
                if stickers:
                    return slot, int(uid), int(stickers[0]["id"])
    # fallback: any sticker in account7
    path = "/opt/telegramforward.old/data/accounts/account7/dm_inbox.json"
    if os.path.isfile(path):
        data = json.load(open(path, encoding="utf-8"))
        for uid, conv in (data.get("conversations") or {}).items():
            for m in conv.get("messages") or []:
                if m.get("media_type") == "sticker" or (m.get("text") or "").strip().lower() == "[sticker]":
                    print("FALLBACK", "account7", uid, conv.get("name"))
                    return "account7", int(uid), int(m["id"])
    return None, None, None

slot, uid, mid = find_denver()
print("TARGET", slot, uid, mid)
if not slot:
    raise SystemExit(0)

from core.dm_media import find_cached_media

print("CACHE_BEFORE", find_cached_media(slot, uid, mid))

from services import dm_inbox_service

async def run():
    hit = await dm_inbox_service.ensure_inbox_media_file(slot, uid, mid)
    print("ENSURE", hit)

asyncio.run(run())
print("CACHE_AFTER", find_cached_media(slot, uid, mid))
