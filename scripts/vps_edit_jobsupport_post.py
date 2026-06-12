#!/usr/bin/env python3
"""Edit @jobsupport0/161879 to match fleet campaign message."""
from __future__ import annotations

import asyncio
import socket
import sys

import paramiko

HOST = "187.127.169.159"
USER = "root"
PASSWORD = "REMOVED_VPS_PASSWORD"

REMOTE_SCRIPT = r'''
import asyncio
import sys

CHANNEL = "@jobsupport0"
MSG_ID = 161879

async def main():
    from core.fleet_defaults import get_fleet_defaults
    from core.account_info_store import load_account_info
    from core import telegram_client

    text = (get_fleet_defaults().get("campaign_message") or "").strip()
    if not text:
        print("ERROR: no campaign_message in fleet defaults", file=sys.stderr)
        sys.exit(1)
    print(f"Editing {CHANNEL}/{MSG_ID} ({len(text)} chars)")

    slots = [f"account{i}" for i in range(1, 11)]
    last_err = None
    for slot in slots:
        info = load_account_info(slot)
        if not info or not info.get("phone"):
            continue
        try:
            async def op(client):
                entity = await client.get_entity(CHANNEL)
                msg = await client.get_messages(entity, ids=MSG_ID)
                if not msg or not getattr(msg, "id", None):
                    raise RuntimeError("message not found")
                old = (msg.message or "")[:80]
                edited = await client.edit_message(entity, MSG_ID, text)
                new = (edited.message or text)[:80]
                return old, new

            old, new = await telegram_client.run_dm_operation(
                slot, op, attach_inbox_handlers=False,
            )
            print(f"OK via {slot}")
            print(f"OLD: {old!r}")
            print(f"NEW: {new!r}")
            return
        except Exception as e:
            last_err = f"{slot}: {e}"
            print(f"TRY {slot}: FAIL — {e}")

    print(f"ERROR: no account could edit post. Last: {last_err}", file=sys.stderr)
    sys.exit(1)

asyncio.run(main())
'''


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sock = socket.create_connection((HOST, 22), timeout=30)
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(hostname=HOST, username=USER, password=PASSWORD, sock=sock)
    cmd = (
        "cd /opt/telegramforward.old && set -a && . ./.env && set +a && "
        f"PYTHONPATH=. ./venv/bin/python - <<'PY'\n{REMOTE_SCRIPT}\nPY"
    )
    _, stdout, stderr = client.exec_command(cmd, timeout=180)
    out = stdout.read().decode("utf-8", errors="replace")
    err = stderr.read().decode("utf-8", errors="replace")
    print(out)
    if err.strip():
        print(err, file=sys.stderr)
    code = stdout.channel.recv_exit_status()
    client.close()
    if code != 0:
        raise SystemExit(code)


if __name__ == "__main__":
    main()
