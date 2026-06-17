"""Find failed document/media messages and test ensure_inbox_media."""

from __future__ import annotations

import os
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

REMOTE_SCRIPT = r'''
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
'''


def main() -> None:
    import paramiko

    pw = os.environ.get("VPS_PASSWORD", "")
    if not pw:
        print("Set VPS_PASSWORD")
        sys.exit(1)
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    local = os.path.join(root, "scripts", "_docs_debug_remote.py")
    with open(local, "w", encoding="utf-8") as f:
        f.write(REMOTE_SCRIPT)
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect("187.127.169.159", username="root", password=pw, timeout=30)
    sftp = ssh.open_sftp()
    sftp.put(local, "/opt/telegramforward.old/scripts/_docs_debug_remote.py")
    sftp.close()
    _, o, e = ssh.exec_command(
        "cd /opt/telegramforward.old && ./venv/bin/python scripts/_docs_debug_remote.py",
        timeout=180,
    )
    print(o.read().decode())
    if e.read().decode().strip():
        print("ERR", e.read().decode())
    ssh.close()


if __name__ == "__main__":
    main()
