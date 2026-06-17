"""Deploy restored Candidates panel + backend stores to production."""
from __future__ import annotations

import os
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# Reuse responsive deploy file list (includes candidates restore).
from _vps_deploy_responsive import FILES, HOST, REMOTE, REMOTE_CMDS, USER  # type: ignore

PASSWORD = os.environ.get("VPS_PASSWORD", "")


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
        if not os.path.isfile(local):
            print(f"  SKIP missing {rel}")
            continue
        remote = f"{REMOTE}/{rel}"
        remote_dir = os.path.dirname(remote).replace("\\", "/")
        parts = remote_dir.split("/")
        path = ""
        for p in parts:
            if not p:
                continue
            path += f"/{p}"
            try:
                sftp.stat(path)
            except OSError:
                try:
                    sftp.mkdir(path)
                except OSError:
                    pass
        print(f"  upload {rel}")
        sftp.put(local, remote)

    sftp.close()

    for cmd in REMOTE_CMDS + [
        "pm2 restart telegram-backend 2>/dev/null || true",
        "curl -s http://127.0.0.1:8000/health | head -c 200",
    ]:
        print(f"\n>>> {cmd}")
        _, stdout, stderr = client.exec_command(cmd, get_pty=True, timeout=600)
        out = stdout.read().decode(errors="replace")
        err = stderr.read().decode(errors="replace")
        code = stdout.channel.recv_exit_status()
        if out:
            print(out[-6000:] if len(out) > 6000 else out)
        if err.strip():
            print(err[-2000:], file=sys.stderr)
        if code != 0 and "npm run build" in cmd:
            print(f"exit {code}", file=sys.stderr)
            client.close()
            return code

    client.close()
    print("\nCandidates deploy done.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
