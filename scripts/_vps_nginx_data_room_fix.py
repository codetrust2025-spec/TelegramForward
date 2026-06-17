"""Add data-room to nginx API proxy regex (fixes HTML instead of JSON in Data room tab)."""
from __future__ import annotations

import os
import sys

import paramiko

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

PWD = os.environ.get("VPS_PASSWORD", "")
HOST = "187.127.169.159"
NGINX = "/etc/nginx/sites-available/telegramforward"

# Insert before favicon (common anchor in production config)
ANCHORS = (
    ("|candidates|metrics|", "|candidates|data-room|metrics|"),
    ("|candidates|", "|candidates|data-room|"),
    ("|fleet|forward-message|favicon", "|fleet|forward-message|data-room|favicon"),
    ("|fleet|favicon", "|fleet|data-room|favicon"),
    ("|workspace|analytics|", "|workspace|analytics|data-room|"),
)


def main() -> int:
    if not PWD:
        print("Set VPS_PASSWORD", file=sys.stderr)
        return 1

    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(HOST, username="root", password=PWD, timeout=30)

    _, o, _ = c.exec_command(f"grep -n 'location ~' {NGINX}", timeout=30)
    line = o.read().decode()
    print("before:", line.strip()[:240])

    if "data-room" in line:
        print("already has data-room")
    else:
        sftp = c.open_sftp()
        with sftp.open(NGINX, "r") as f:
            content = f.read().decode("utf-8")
        patched = False
        for old, new in ANCHORS:
            if old in content and new not in content:
                content = content.replace(old, new, 1)
                patched = True
                print(f"patched via anchor: {old[:40]}...")
                break
        if not patched:
            raise SystemExit(f"Could not find anchor in {NGINX}; manual nginx edit needed")
        with sftp.open(NGINX, "w") as f:
            f.write(content.encode("utf-8"))
        sftp.close()

    for cmd in [
        "nginx -t 2>&1",
        "systemctl reload nginx",
        "grep -n 'data-room' /etc/nginx/sites-available/telegramforward | head -3",
        'curl -s -o /dev/null -w "data-room:%{http_code} %{content_type}\\n" '
        "http://127.0.0.1:8000/data-room/stats",
        'curl -s http://127.0.0.1:8000/data-room/stats | head -c 120',
        'curl -s -o /dev/null -w "https:%{http_code} %{content_type}\\n" '
        "https://teleautomation.online/data-room/stats",
        'curl -s https://teleautomation.online/data-room/stats | head -c 120',
    ]:
        print(">>>", cmd[:100])
        _, o, e = c.exec_command(cmd, timeout=60)
        out = o.read().decode("utf-8", errors="replace")
        err = e.read().decode("utf-8", errors="replace")
        if out.strip():
            print(out[:500])
        if err.strip():
            print(err[:300], file=sys.stderr)

    c.close()
    print("\nDone — hard refresh Data room tab.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
