"""Probe WA Deploy Test conversation keys on VPS."""
from __future__ import annotations

import os
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HOST = "187.127.169.159"
REMOTE = "/opt/telegramforward"
PY = f"{REMOTE}/venv/bin/python"
PASSWORD = os.environ.get("VPS_PASSWORD", "")


def main() -> int:
    import paramiko

    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(HOST, username="root", password=PASSWORD, timeout=30)

    cmd = (
        f"cd {REMOTE} && PYTHONPATH={REMOTE} {PY} -c "
        "\"from core.config import ACCOUNTS; from core.dm_store import load_inbox; "
        "from core.account_info_store import load_account_info; "
        "[print('ACC', s, load_account_info(s)) for s in ACCOUNTS]; "
        "print('PRADEEP', '6300690917' in (load_inbox('account9').get('conversations') or {})); "
        "[print('CONV', s, k, c.get('name'), c.get('user_id'), c.get('phone_e164')) "
        "for s in ACCOUNTS for k,c in (load_inbox(s).get('conversations') or {}).items() "
        "if 'Deploy' in (c.get('name') or '')]\""
    )
    _, o, e = ssh.exec_command(cmd, timeout=60)
    print(o.read().decode())
    print(e.read().decode())
    ssh.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
