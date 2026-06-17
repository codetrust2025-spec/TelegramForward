"""Wake Karthik: catch up pending inbox replies on live VPS."""
from __future__ import annotations

import os
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

REMOTE = "/opt/telegramforward.old"
HOST = "187.127.169.159"
PASSWORD = os.environ.get("VPS_PASSWORD", "")

REMOTE_SCRIPT = r'''
import asyncio
import json
import os
import sys

sys.path.insert(0, "/opt/telegramforward.old")
os.chdir("/opt/telegramforward.old")

from dotenv import load_dotenv
load_dotenv("/opt/telegramforward.old/.env", override=False)


async def main():
    from core import ai_smart_reply
    from core.karthik_inbox_sweep import start as start_sweep, status as sweep_status

    print("ai_enabled", ai_smart_reply.is_enabled())
    print("health", json.dumps(ai_smart_reply.health(), default=str))

    start_sweep()
    pending = ai_smart_reply.list_pending_inbound_targets()
    print("pending_count", len(pending))

    result = await ai_smart_reply.catch_up_pending_replies(max_replies=15, force=True)
    print("catch_up", json.dumps(result, default=str))

    # Give workers time to drain AI tasks
    await asyncio.sleep(20)

    pending_after = ai_smart_reply.list_pending_inbound_targets()
    print("pending_after", len(pending_after))
    print("sweep_status", json.dumps(sweep_status(), default=str))


asyncio.run(main())
'''


def main() -> int:
    if not PASSWORD:
        print("VPS_PASSWORD not set", file=sys.stderr)
        return 1

    import paramiko

    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(HOST, username="root", password=PASSWORD, timeout=30)

    remote_path = f"{REMOTE}/scripts/_wake_karthik_once.py"
    sftp = client.open_sftp()
    with sftp.open(remote_path, "w") as f:
        f.write(REMOTE_SCRIPT)
    sftp.close()

    cmd = f"cd {REMOTE} && ./venv/bin/python scripts/_wake_karthik_once.py"
    stdin, stdout, stderr = client.exec_command(cmd, timeout=180)
    out = stdout.read().decode("utf-8", errors="replace")
    err = stderr.read().decode("utf-8", errors="replace")
    print(out)
    if err.strip():
        print("STDERR:", err, file=sys.stderr)

    stdin, stdout, stderr = client.exec_command(
        "pm2 logs telegram-backend --lines 100 --nostream 2>&1 | grep -i ai_smart | tail -20",
        timeout=60,
    )
    print("\n>>> ai_smart_reply logs")
    print(stdout.read().decode("utf-8", errors="replace"))

    client.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
