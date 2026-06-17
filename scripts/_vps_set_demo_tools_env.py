"""Set DEMO_TOOLS_* URLs on VPS .env and restart backend."""
from __future__ import annotations

import os
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HOST = "187.127.169.159"
REMOTE = "/opt/telegramforward"
ENV_PATH = f"{REMOTE}/.env"

# User mapping: 1=Windows LockedIn, 2=Mac LockedIn, 3=UltraViewer
URLS = {
    "DEMO_TOOLS_LOCKEDIN_WINDOWS_URL": (
        "https://drive.google.com/file/d/1V3NtInme78gzzSdy_czbHsc6syVlxdX6/view?usp=drive_link"
    ),
    "DEMO_TOOLS_LOCKEDIN_MAC_URL": (
        "https://drive.google.com/file/d/112BOrpLe2hjROCqsv4wTJrt-xwFwYa7M/view?usp=drive_link"
    ),
    "DEMO_TOOLS_ULTRAVIEWER_URL": (
        "https://drive.google.com/file/d/1uDYKIqRqkkHQ9YoLQQJY6LDThDpiUy_5/view?usp=drive_link"
    ),
}

# Clear legacy keys that used the wrong mapping
REMOVE_KEYS = ("DEMO_TOOLS_LOCKEDIN_URL", "DEMO_TOOLS_FOLDER_URL")


def main() -> int:
    pwd = os.environ.get("VPS_PASSWORD", "")
    if not pwd:
        print("VPS_PASSWORD not set", file=sys.stderr)
        return 1

    import paramiko

    repo = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    local_demo = os.path.join(repo, "features", "demo_tools.py")
    remote_demo = f"{REMOTE}/features/demo_tools.py"

    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(HOST, username="root", password=pwd, timeout=30)
    sftp = c.open_sftp()
    sftp.put(local_demo, remote_demo)
    sftp.close()
    print(f"uploaded {remote_demo}")

    lines = []
    for key in REMOVE_KEYS:
        lines.append(f"sed -i '/^{key}=/d' {ENV_PATH} 2>/dev/null || true")

    for key, val in URLS.items():
        lines.append(f"if grep -q '^{key}=' {ENV_PATH} 2>/dev/null; then")
        lines.append(f"  sed -i 's|^{key}=.*|{key}={val}|' {ENV_PATH}")
        lines.append("else")
        lines.append(f"  echo '{key}={val}' >> {ENV_PATH}")
        lines.append("fi")

    script = "\n".join(lines) + "\n"
    script += (
        f"grep '^DEMO_TOOLS_' {ENV_PATH}\n"
        f"set -a && . {ENV_PATH} && set +a && cd {REMOTE} && PYTHONPATH={REMOTE} "
        f"{REMOTE}/venv/bin/python -c "
        "\"from features.demo_tools import _compose_message; m=_compose_message(); "
        "print('preview_ok', bool(m)); print(m[:280] if m else 'empty')\"\n"
        "pm2 restart telegram-backend\n"
        "sleep 3\n"
        "curl -sf http://127.0.0.1:8000/health\n"
    )

    _, o, e = c.exec_command(script, timeout=90)
    out = (o.read() + e.read()).decode("utf-8", errors="replace")
    print(out)
    c.close()
    return 0 if "preview_ok True" in out else 1


if __name__ == "__main__":
    raise SystemExit(main())
