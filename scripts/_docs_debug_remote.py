
import asyncio, glob, json, os, sys
sys.path.insert(0, "/opt/telegramforward.old")
os.chdir("/opt/telegramforward.old")

from services import dm_inbox_service
from core.dm_media import find_cached_media

NAMES = ("spider", "saaho")

def targets():
    for path in glob.glob("/opt/telegramforward.old/data/accounts/*/dm_inbox.json"):
        slot = path.split("/")[-2]
        data = json.load(open(path, encoding="utf-8"))
        for uid, conv in (data.get("conversations") or {}).items():
            label = ((conv.get("name") or "") + " " + (conv.get("username") or "")).lower()
            if not any(n in label for n in NAMES):
                continue
            for m in conv.get("messages") or []:
                mt = m.get("media_type") or ""
                text = (m.get("text") or "").strip().lower()
                if not m.get("media") and mt not in ("document", "photo", "video", "sticker", "media"):
                    continue
                if m.get("media") or mt in ("document", "media", "photo", "sticker", "video"):
                    yield slot, int(uid), conv.get("name"), m

async def main():
    for slot, uid, name, m in list(targets())[:8]:
        mid = int(m["id"])
        mt = m.get("media_type")
        text = (m.get("text") or "")[:60]
        before = find_cached_media(slot, uid, mid)
        hit = await dm_inbox_service.ensure_inbox_media_file(slot, uid, mid)
        after = find_cached_media(slot, uid, mid)
        print(f"{name} {slot} {uid} id={mid} type={mt} text={text!r}")
        print(f"  before={before} ensure={hit} after={after}")

asyncio.run(main())
