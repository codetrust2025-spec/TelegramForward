"""New JS filename (app-[hash].js) + confirm patch + sw cache clear."""
from __future__ import annotations

import os
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import paramiko

HOST, USER, REMOTE = "187.127.169.159", "root", "/opt/telegramforward"
PWD = os.environ.get("VPS_PASSWORD", "")
REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

PATCH_SCRIPT = os.path.join(REPO, "scripts", "_patch_confirm.js")


def main() -> int:
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(HOST, username=USER, password=PWD, timeout=30)
    sftp = c.open_sftp()

    uploads = [
        ("dashboard/vite.config.js", f"{REMOTE}/dashboard/vite.config.js"),
        ("dashboard/src/context/ConfirmContext.jsx", f"{REMOTE}/dashboard/src/context/ConfirmContext.jsx"),
        ("static/sw.js", f"{REMOTE}/static/sw.js"),
    ]
    for rel, remote in uploads:
        sftp.put(os.path.join(REPO, rel.replace("/", os.sep)), remote)
        print("upload", rel)
    sftp.close()

    _, o, _ = c.exec_command(f"cd {REMOTE}/dashboard && npm run build 2>&1 | tail -16", timeout=600)
    print(o.read().decode("utf-8", errors="replace"))

    c.exec_command(f"mkdir -p {REMOTE}/scripts")[1].channel.recv_exit_status()
    sftp = c.open_sftp()
    sftp.put(PATCH_SCRIPT, f"{REMOTE}/scripts/_patch_confirm.js")
    sftp.close()

    _, o, e = c.exec_command(f"cd {REMOTE} && node scripts/_patch_confirm.js", timeout=60)
    print(o.read().decode("utf-8", errors="replace"))
    err = e.read().decode("utf-8", errors="replace")
    if err.strip():
        print("stderr:", err[:400])

    _, o, _ = c.exec_command(
        f"grep -o 'app-[^.]*.js' {REMOTE}/static/index.html && "
        f"curl -sI https://teleautomation.online/ | grep -i cache",
        timeout=30,
    )
    print(o.read().decode("utf-8", errors="replace"))

    c.close()
    print("Done — open site in Incognito or clear site data once")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
