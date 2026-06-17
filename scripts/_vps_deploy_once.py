"""One-shot VPS deploy for forwarding mode (paramiko)."""
from __future__ import annotations

import os
import sys

HOST = "187.127.169.159"
USER = "root"
REMOTE = "/opt/telegramforward"
PASSWORD = os.environ.get("VPS_PASSWORD", "")

FILES = [
    "core/posting_mode.py",
    "features/interval_forward.py",
    "workers/account_worker.py",
    "workers/account_state.py",
    "server.py",
    "services/account_manager.py",
    "dashboard/src/App.jsx",
    "dashboard/src/components/CandidatesPanel.jsx",
    "dashboard/src/main.jsx",
    "dashboard/src/index.css",
    "dashboard/src/responsive.css",
    "dashboard/src/components/AccountCard.jsx",
    "dashboard/src/components/AccountPanel.jsx",
    "dashboard/src/components/PostingModePanel.jsx",
    "dashboard/src/utils/tabUnreadBadge.js",
    "dashboard/src/utils/inboxUnread.js",
    "dashboard/index.html",
]

REMOTE_CMDS = [
    f"cd {REMOTE}/dashboard && npm run build",
    f"node {REMOTE}/scripts/_patch_confirm.js",
    f"cd {REMOTE} && bash scripts/production_update.sh",
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

    for cmd in REMOTE_CMDS:
        print(f"\n>>> {cmd}")
        stdin, stdout, stderr = client.exec_command(cmd, get_pty=True, timeout=600)
        out = stdout.read().decode(errors="replace")
        err = stderr.read().decode(errors="replace")
        code = stdout.channel.recv_exit_status()
        if out:
            text = out[-8000:] if len(out) > 8000 else out
            print(text.encode("utf-8", errors="replace").decode("utf-8", errors="replace"))
        if err:
            text = err[-4000:] if len(err) > 4000 else err
            print(text.encode("utf-8", errors="replace").decode("utf-8", errors="replace"), file=sys.stderr)
        if code != 0:
            print(f"Command failed exit={code}", file=sys.stderr)
            client.close()
            return code

    # Verify JS bundle contains new UI strings
    verify_cmd = (
        f"grep -l 'Message to send' {REMOTE}/static/assets/*.js 2>/dev/null | head -1; "
        f"python3 -c \"import sys; sys.path.insert(0,'{REMOTE}'); "
        f"from core.posting_mode import SOURCE_TEMPLATE, load_posting_mode; "
        f"print('backend_ok', SOURCE_TEMPLATE, load_posting_mode('account1').forwarding.source_type)\""
    )
    stdin, stdout, stderr = client.exec_command(verify_cmd, timeout=60)
    verify_out = stdout.read().decode().strip()
    print("\nVerify:", verify_out or "(grep found nothing — check vite outDir)")

    client.close()
    print("\nDeploy finished OK.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
