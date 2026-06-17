"""Find and delete WA Deploy Test inbox thread on VPS."""
from __future__ import annotations

import os
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HOST = "187.127.169.159"
REMOTE = "/opt/telegramforward"
PY = f"{REMOTE}/venv/bin/python"
PASSWORD = os.environ.get("VPS_PASSWORD", "")


def main() -> int:
    if not PASSWORD:
        print("VPS_PASSWORD not set", file=sys.stderr)
        return 1

    import paramiko

    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(HOST, username="root", password=PASSWORD, timeout=30)

    probe = (
        f"cd {REMOTE} && PYTHONPATH={REMOTE} {PY} <<'PYEOF'\n"
        """import asyncio
from core.config import ACCOUNTS
from core.dm_store import load_inbox
from core.whatsapp_identity import phone_to_synthetic_user_id
from services import dm_inbox_service

hits = []
for slot in ACCOUNTS:
    for k, conv in (load_inbox(slot).get("conversations") or {}).items():
        name = (conv.get("name") or "").strip()
        phone = str(conv.get("phone_e164") or "")
        if name == "WA Deploy Test" or (name and "WA Deploy" in name):
            hits.append((slot, k, name, phone, conv.get("user_id")))

print("FOUND", len(hits))
for slot, key, name, phone, uid in hits:
    print("DELETE", slot, key, name, phone, uid)
    data = load_inbox(slot)
    convs = data.get("conversations") or {}
    if key not in convs:
        print("RESULT missing_key")
        continue
    del convs[key]
    data["conversations"] = convs
    from core.dm_store import save_inbox
    save_inbox(slot, data)
    if uid is not None:
        try:
            uid_i = int(uid)
            result = asyncio.run(dm_inbox_service.delete_conversation(slot, uid_i))
            print("CRM_CLEAN", result)
        except (TypeError, ValueError):
            pass
    print("RESULT ok")

try:
    from core.contact_link_store import list_links, unlink_phone
    removed = 0
    for link in list_links():
        phone = str(link.get("phone_e164") or "")
        if "9876543210" in phone and unlink_phone(phone):
            removed += 1
    if removed:
        print("CONTACT_LINKS_REMOVED", removed)
except Exception as e:
    print("LINK_SKIP", repr(e))
PYEOF
"""
    )
    _, stdout, stderr = ssh.exec_command(probe, timeout=90)
    out = stdout.read().decode("utf-8", errors="replace")
    err = stderr.read().decode("utf-8", errors="replace")
    if out.strip():
        print(out)
    if err.strip():
        print(err, file=sys.stderr)
    ssh.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
