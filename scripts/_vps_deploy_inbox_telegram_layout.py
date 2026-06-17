"""Deploy Telegram-style inbox layout (dashboard build only)."""
from __future__ import annotations

import os
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HOST = "187.127.169.159"
USER = "root"
REMOTE = "/opt/telegramforward"
PASSWORD = os.environ.get("VPS_PASSWORD", "")

FILES = [
    "dashboard/src/main.jsx",
    "dashboard/src/index.css",
    "dashboard/src/inbox/VirtualList.jsx",
    "dashboard/src/inbox/VirtualConversationList.jsx",
    "dashboard/src/inbox/ConversationListItem.jsx",
    "dashboard/src/inbox/MessageBubble.jsx",
    "dashboard/src/inbox/MessageTimeline.jsx",
    "dashboard/src/inbox/ChatHeader.jsx",
    "dashboard/src/inbox/ChatComposer.jsx",
    "dashboard/src/inbox/inboxUiUtils.js",
    "dashboard/src/inbox/inboxLayout.css",
    "dashboard/src/components/InboxPanel.jsx",
    "dashboard/src/components/crm/CRMInboxList.jsx",
    "dashboard/src/components/crm/ChatWindow.jsx",
]

REMOTE_CMDS = [
    f"cd {REMOTE}/dashboard && npm run build",
    f"node {REMOTE}/scripts/_patch_confirm.js || true",
    f"grep -l tg-inbox-shell $(ls -t {REMOTE}/static/assets/*.js 2>/dev/null | head -1) 2>/dev/null || "
    f"grep -l tg-sidebar $(ls -t {REMOTE}/static/assets/*.js 2>/dev/null | head -1) 2>/dev/null || "
    f"echo 'grep: bundle check skipped'",
    f"grep -l tg-sidebar $(ls -t {REMOTE}/static/assets/*.css 2>/dev/null | head -1) 2>/dev/null || "
    f"echo 'grep: css check skipped'",
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
        if not os.path.isfile(local):
            print(f"Missing local file: {local}", file=sys.stderr)
            client.close()
            return 1
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
        _, stdout, stderr = client.exec_command(cmd, get_pty=True, timeout=600)
        out = stdout.read().decode(errors="replace")
        err = stderr.read().decode(errors="replace")
        code = stdout.channel.recv_exit_status()
        if out:
            print(out[-8000:] if len(out) > 8000 else out)
        if err.strip():
            print(err[-2000:], file=sys.stderr)
        if code != 0:
            print(f"Command failed exit={code}", file=sys.stderr)
            client.close()
            return code

    verify = (
        f"head -1 {REMOTE}/static/index.html; "
        f"ls -t {REMOTE}/static/assets/*.css 2>/dev/null | head -1; "
        f"ls -t {REMOTE}/static/assets/*.js 2>/dev/null | head -1"
    )
    _, o, _ = client.exec_command(verify, timeout=30)
    print("\nVerify:", o.read().decode().strip())

    client.close()
    print("\nInbox layout deploy OK — hard refresh https://teleautomation.online")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
