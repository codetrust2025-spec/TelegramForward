"""Deploy dm_store key fix and repair malformed inbox conversation keys on VPS."""
from __future__ import annotations

import os
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HOST = "187.127.169.159"
REMOTE = "/opt/telegramforward"
PASSWORD = os.environ.get("VPS_PASSWORD", "")
PY = f"{REMOTE}/venv/bin/python"


def main() -> int:
    if not PASSWORD:
        print("VPS_PASSWORD not set", file=sys.stderr)
        return 1

    import paramiko

    repo = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(HOST, username="root", password=PASSWORD, timeout=30)
    sftp = ssh.open_sftp()

    for rel in ["core/dm_store.py"]:
        local = os.path.join(repo, rel.replace("/", os.sep))
        remote = f"{REMOTE}/{rel}"
        sftp.put(local, remote)
        old_remote = f"{REMOTE}.old/{rel}"
        try:
            sftp.put(local, old_remote)
        except OSError:
            pass
        print(f"uploaded {rel}")

    sftp.close()

    cmd = (
        f"cd {REMOTE} && PYTHONPATH={REMOTE} {PY} -c "
        "\"from core.config import ACCOUNTS; from core.dm_store import repair_conversation_keys, load_inbox; "
        "total=[]; "
        "[total.extend([(s,r) for r in repair_conversation_keys(s)]) for s in ACCOUNTS]; "
        "bad=[(s,k) for s in ACCOUNTS for k in (load_inbox(s).get('conversations') or {}) "
        "if not str(k).lstrip('-').isdigit()]; "
        "print('REPAIRS', total); print('REMAINING_BAD', bad)\""
    )
    _, o, e = ssh.exec_command(cmd, timeout=90)
    print(o.read().decode())
    err = e.read().decode().strip()
    if err:
        print(err, file=sys.stderr)

    _, o2, _ = ssh.exec_command(
        f"cd {REMOTE} && PYTHONPATH={REMOTE} pm2 restart telegram-backend --update-env",
        timeout=60,
    )
    print(o2.read().decode()[-400:])

    ssh.close()
    print("done")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
