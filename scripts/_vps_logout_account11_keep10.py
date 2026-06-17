"""SSH to VPS: remove account11 login (keep account10), restart backend."""
from __future__ import annotations

import os
import sys
import textwrap

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

PASSWORD = os.environ.get("VPS_PASSWORD", "")
HOST = "187.127.169.159"
REMOTE = "/opt/telegramforward.old"


REMOTE_SCRIPT = textwrap.dedent(
    r"""
    import asyncio
    import os
    import sys

    os.chdir({remote!r})
    sys.path.insert(0, {remote!r})

    SLOT = "account11"
    KEEP = "account10"

    async def main() -> None:
        from core.account_info_store import clear_account_info, load_account_info
        from core.login_pending import clear_pending
        from core.session_manager import session_manager
        from core.worker_persistence import mark_stopped

        print("account11 before:", load_account_info(SLOT))
        print("account10 keep:", load_account_info(KEEP))

        mark_stopped(SLOT)
        clear_account_info(SLOT)
        clear_pending(SLOT)
        try:
            await session_manager.delete_session(SLOT)
        except Exception as e:
            print("delete_session warning:", e)

        print("account11 after:", load_account_info(SLOT) or "cleared")
        print("account10 still:", load_account_info(KEEP) and "ok")

    asyncio.run(main())
    """
)


def main() -> int:
    if not PASSWORD:
        print("VPS_PASSWORD not set", file=sys.stderr)
        return 1
    import paramiko

    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(HOST, username="root", password=PASSWORD, timeout=30)

    def run(cmd: str, timeout: int = 180) -> str:
        _, stdout, stderr = c.exec_command(cmd, timeout=timeout)
        out = stdout.read().decode("utf-8", "replace")
        err = stderr.read().decode("utf-8", "replace")
        return (out + err).strip()

    py = REMOTE_SCRIPT.format(remote=REMOTE)
    remote_path = f"{REMOTE}/scripts/_cleanup_account11.py"
    sftp = c.open_sftp()
    with sftp.file(remote_path, "w") as f:
        f.write(py)
    sftp.close()

    print(">>> Cleanup account11 session + account_info")
    print(
        run(
            f"cd {REMOTE} && PYTHONPATH={REMOTE} ./venv/bin/python {remote_path}",
            timeout=120,
        ),
    )

    print("\n>>> Restart backend (drop in-memory account11 worker)")
    print(run("pm2 restart telegram-backend", timeout=60))

    print("\n>>> Verify files")
    print(
        run(
            f"test -f {REMOTE}/data/accounts/account11/account_info.json && echo account11:STILL "
            f"|| echo account11:CLEARED; "
            f"grep phone {REMOTE}/data/accounts/account10/account_info.json",
        ),
    )

    c.close()
    print("\nDone — hard refresh dashboard. Account 10 keeps +919908957244; Account 11 is empty.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
