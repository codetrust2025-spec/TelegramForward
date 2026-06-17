"""Debug sticker media for Denver / Kalyan on VPS."""

from __future__ import annotations

import os
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HOST = "187.127.169.159"
REMOTE = "/opt/telegramforward.old"
PASSWORD = os.environ.get("VPS_PASSWORD", "")


def main() -> None:
    import paramiko

    if not PASSWORD:
        print("Set VPS_PASSWORD")
        sys.exit(1)

    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(HOST, username="root", password=PASSWORD, timeout=30)
    sftp = ssh.open_sftp()
    local = os.path.join(os.path.dirname(__file__), "_sticker_debug_remote.py")
    remote = f"{REMOTE}/scripts/_sticker_debug_remote.py"
    with open(local, "w", encoding="utf-8") as f:
        f.write(REMOTE_SCRIPT)
    sftp.put(local, remote)
    sftp.close()
    _, o, e = ssh.exec_command(
        f"cd {REMOTE} && ./venv/bin/python scripts/_sticker_debug_remote.py",
        timeout=120,
    )
    print(o.read().decode())
    err = e.read().decode()
    if err:
        print("STDERR:", err)
    _, o2, _ = ssh.exec_command(
        "ls -la /opt/telegramforward.old/data/accounts/account7/dm_media_cache/7282523499_* 2>/dev/null; "
        "file /opt/telegramforward.old/data/accounts/account7/dm_media_cache/7282523499_* 2>/dev/null",
        timeout=30,
    )
    print(o2.read().decode())
    ssh.close()


REMOTE_SCRIPT = r'''import asyncio, glob, json, os, sys
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
'''


if __name__ == "__main__":
    main()
