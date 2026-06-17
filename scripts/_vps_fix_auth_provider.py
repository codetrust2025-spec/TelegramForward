"""Fix TeleAutomationApp missing AuthProvider wrapper on VPS."""
from __future__ import annotations

import os
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import paramiko

HOST, USER, REMOTE = "187.127.169.159", "root", "/opt/telegramforward"
PATH = f"{REMOTE}/dashboard/src/teleautomation-app.jsx"
PWD = os.environ.get("VPS_PASSWORD", "")

BROKEN = """export default function TeleAutomationApp() {
  return <SR />
}"""

FIXED = """export default function TeleAutomationApp() {
  return <_Component46><SR /></_Component46>
}"""

LOADING_OLD = 'return <div className="auth-screen"><Rs size={32} /></div>;'
LOADING_NEW = (
    'return <div className="auth-screen"><Rs size={32} />'
    '<p className="auth-loading-label">Loading…</p></div>;'
)


def main() -> int:
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(HOST, username=USER, password=PWD, timeout=30)
    sftp = c.open_sftp()

    with sftp.open(PATH, "r") as f:
        text = f.read().decode("utf-8")

    changed = False
    if BROKEN in text:
        text = text.replace(BROKEN, FIXED, 1)
        print("Patched TeleAutomationApp AuthProvider wrapper")
        changed = True
    elif FIXED.strip() in text:
        print("AuthProvider wrap OK")
    else:
        print("ERROR: TeleAutomationApp export not found", file=sys.stderr)
        sftp.close()
        c.close()
        return 1

    if LOADING_OLD in text and LOADING_NEW not in text:
        text = text.replace(LOADING_OLD, LOADING_NEW, 1)
        print("Patched auth loading label")
        changed = True
    elif LOADING_NEW in text:
        print("Auth loading label OK")

    if changed:
        with sftp.open(PATH, "w") as f:
            f.write(text.encode("utf-8"))

    sftp.close()

    _, o, _ = c.exec_command(f"cd {REMOTE}/dashboard && npm run build 2>&1 | tail -12", timeout=600)
    print(o.read().decode("utf-8", errors="replace"))

    _, o, _ = c.exec_command(f"grep -o 'index-[^.]*.js' {REMOTE}/static/index.html", timeout=30)
    bundle = o.read().decode().strip()
    print("bundle:", bundle)

    c.close()
    print("Done — hard refresh teleautomation.online")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
