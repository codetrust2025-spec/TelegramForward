"""Deploy automatic 24h stats reset to production VPS."""
from __future__ import annotations

import os
import sys

HOST = "187.127.169.159"
USER = "root"
REMOTE = "/opt/telegramforward"
PASSWORD = os.environ.get("VPS_PASSWORD", "")

FILES = [
    "core/stats_reset.py",
    "core/daily_stats.py",
    "services/account_manager.py",
    "services/dm_inbox_service.py",
    "server.py",
]

REMOTE_CMDS = [
    f"pm2 restart telegram-backend",
    f"sleep 3 && curl -sf -m 5 http://127.0.0.1:8000/health && echo HEALTH_OK",
]


def main() -> int:
    if not PASSWORD:
        print("VPS_PASSWORD not set", file=sys.stderr)
        return 1

    import paramiko

    repo = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    print(f"Connecting to {USER}@{HOST}...")
    client.connect(HOST, username=USER, password=PASSWORD, timeout=30)
    sftp = client.open_sftp()

    for rel in FILES:
        local = os.path.join(repo, rel.replace("/", os.sep))
        remote = f"{REMOTE}/{rel}"
        print(f"  upload {rel}")
        sftp.put(local, remote)

    sftp.close()

    for cmd in REMOTE_CMDS:
        print(f"\n>>> {cmd}")
        stdin, stdout, stderr = client.exec_command(cmd, get_pty=True, timeout=120)
        out = stdout.read().decode(errors="replace")
        err = stderr.read().decode(errors="replace")
        code = stdout.channel.recv_exit_status()
        if out:
            text = out[-4000:] if len(out) > 4000 else out
            print(text.encode("utf-8", errors="replace").decode("utf-8", errors="replace"))
        if err:
            text = err[-2000:] if len(err) > 2000 else err
            print(text.encode("utf-8", errors="replace").decode("utf-8", errors="replace"), file=sys.stderr)
        if code != 0:
            print(f"Command failed exit={code}", file=sys.stderr)
            client.close()
            return code

    verify_cmd = (
        f"python3 -c \"import sys; sys.path.insert(0,'{REMOTE}'); "
        f"from core.stats_reset import maybe_auto_reset_24h; "
        f"print('backend_ok', maybe_auto_reset_24h.__name__)\""
    )
    stdin, stdout, stderr = client.exec_command(verify_cmd, timeout=30)
    print("\nVerify:", stdout.read().decode().strip())

    client.close()
    print("\nDeploy finished OK.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
