#!/usr/bin/env python3
"""Post new message to @jobsupport0 and repoint forwarding fleet."""
from __future__ import annotations

import socket
import sys

import paramiko

HOST = "187.127.169.159"
USER = "root"
PASSWORD = "8897870998s@SS"

REMOTE = r'''
import asyncio
import json
import sys
import time

CHANNEL = "@jobsupport0"
FWD = ["account1", "account2", "account4", "account6", "account9"]

async def post_new():
    from core.fleet_defaults import get_fleet_defaults
    from core.account_info_store import load_account_info
    from core import telegram_client
    from core.posting_mode import set_forwarding_source

    text = (get_fleet_defaults().get("campaign_message") or "").strip()
    if not text:
        sys.exit("no campaign text")

    slots = [f"account{i}" for i in range(1, 11)]
    post_slot = None
    new_id = None

    for slot in slots:
        info = load_account_info(slot)
        if not info or not info.get("phone"):
            continue
        try:
            async def op(client):
                entity = await client.get_entity(CHANNEL)
                msg = await client.send_message(entity, text)
                return msg.id, (msg.message or "")[:100]

            mid, preview = await telegram_client.run_dm_operation(
                slot, op, attach_inbox_handlers=False,
            )
            return slot, mid, preview
        except Exception as e:
            print(f"POST TRY {slot}: {e}")

    return None, None, None

async def main():
    import urllib.request, http.cookiejar

    post_slot, new_id, preview = await post_new()
    if not new_id:
        print("ERROR: could not post to channel from any account", file=sys.stderr)
        sys.exit(1)

    print(f"POSTED via {post_slot}: message_id={new_id}")
    print(f"Preview: {preview!r}")
    print(f"Link: https://t.me/jobsupport0/{new_id}")

    from core.fleet_defaults import save_fleet_defaults, get_fleet_defaults
    url = f"https://t.me/jobsupport0/{new_id}"
    save_fleet_defaults(forward_source_url=url)

    from core.posting_mode import set_forwarding_source
    for slot in FWD:
        set_forwarding_source(slot, source_peer=CHANNEL, source_message_id=int(new_id))
        print(f"  repointed {slot} -> {CHANNEL}/{new_id}")

    # restart forwarding workers via API
    from pathlib import Path
    pw = ""
    for line in Path(".env").read_text().splitlines():
        if line.startswith("DASHBOARD_PASSWORD="):
            pw = line.split("=", 1)[1].strip().strip('"').strip("'")
    cj = http.cookiejar.CookieJar()
    op = urllib.request.build_opener(http.cookiejar.HTTPCookieProcessor(cj))
    def call(method, path, body=None):
        import json as j
        data = j.dumps(body).encode() if body else None
        req = urllib.request.Request(
            f"http://127.0.0.1:8000{path}", data=data,
            headers={"Content-Type": "application/json"} if data else {},
            method=method,
        )
        with op.open(req, timeout=60) as r:
            return j.loads(r.read().decode())
    call("POST", "/auth/login", {"username": "admin", "password": pw})
    for slot in FWD:
        call("POST", f"/account/{slot}/stop")
        time.sleep(1)
        call("POST", f"/account/{slot}/start?feature=forwarding")
        print(f"  restarted {slot}")
        time.sleep(1)

    print("DONE")

asyncio.run(main())
'''


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sock = socket.create_connection((HOST, 22), timeout=30)
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(hostname=HOST, username=USER, password=PASSWORD, sock=sock)
    _, stdout, stderr = client.exec_command(
        f"cd /opt/telegramforward.old && set -a && . ./.env && set +a && "
        f"PYTHONPATH=. ./venv/bin/python - <<'PY'\n{REMOTE}\nPY",
        timeout=300,
    )
    print(stdout.read().decode("utf-8", errors="replace"))
    err = stderr.read().decode("utf-8", errors="replace")
    if err.strip():
        print(err, file=sys.stderr)
    code = stdout.channel.recv_exit_status()
    client.close()
    if code != 0:
        raise SystemExit(code)


if __name__ == "__main__":
    main()
