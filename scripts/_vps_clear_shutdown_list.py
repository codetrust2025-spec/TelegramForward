"""Clear all accounts from shutdown rest list on VPS (no stats reset)."""
from __future__ import annotations

import os
import sys
import textwrap

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

PASSWORD = os.environ.get("VPS_PASSWORD", "")
HOST = "187.127.169.159"
REMOTE = "/opt/telegramforward.old"


def main() -> int:
    if not PASSWORD:
        print("VPS_PASSWORD not set", file=sys.stderr)
        return 1
    import paramiko

    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(HOST, username="root", password=PASSWORD, timeout=30)

    py = textwrap.dedent(
        f"""
        import os, sys
        os.chdir({REMOTE!r})
        sys.path.insert(0, {REMOTE!r})
        from core.account_shutdown import clear_all_shutdowns, list_shutdowns

        before = list_shutdowns(active_only=False)
        print("before:", sorted(before.keys()))
        cleared = clear_all_shutdowns()
        print("cleared:", cleared)
        after = list_shutdowns()
        print("after:", sorted(after.keys()) or "(empty)")
        """
    )
    remote_py = f"{REMOTE}/scripts/_clear_shutdown_run.py"
    sftp = c.open_sftp()
    with sftp.file(remote_py, "w") as f:
        f.write(py)
    sftp.close()

    def run(cmd: str, timeout: int = 60) -> str:
        _, stdout, stderr = c.exec_command(cmd, timeout=timeout)
        return (stdout.read() + stderr.read()).decode("utf-8", "replace").strip()

    print(run(f"cd {REMOTE} && PYTHONPATH={REMOTE} ./venv/bin/python {remote_py}"))
    print("\n>>> Restart backend so dashboard picks up empty shutdown list")
    print(run("pm2 restart telegram-backend", timeout=60))
    print("\n>>> Verify file")
    print(run(f"cat {REMOTE}/data/account_shutdown.json"))

    c.close()
    print("\nDone — accounts return to Accounts tab. Start them manually when ready.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
