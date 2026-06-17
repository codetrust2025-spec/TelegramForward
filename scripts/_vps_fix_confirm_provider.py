"""Wrap TeleAutomationApp with ConfirmProvider (required by dashboard hooks)."""
from __future__ import annotations

import os
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import paramiko

HOST, USER, REMOTE = "187.127.169.159", "root", "/opt/telegramforward"
MAIN = f"{REMOTE}/dashboard/src/main.jsx"
PWD = os.environ.get("VPS_PASSWORD", "")
REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

IMPORT = "import { ConfirmProvider } from './context/ConfirmContext.jsx'\n"

OLD_RENDER = """createRoot(document.getElementById('root')).render(
  <StrictMode>
    <TeleAutomationApp />
  </StrictMode>,
)"""

NEW_RENDER = """createRoot(document.getElementById('root')).render(
  <StrictMode>
    <ConfirmProvider>
      <TeleAutomationApp />
    </ConfirmProvider>
  </StrictMode>,
)"""

UPLOADS = [
    ("dashboard/src/context/ConfirmContext.jsx", f"{REMOTE}/dashboard/src/context/ConfirmContext.jsx"),
    ("dashboard/src/components/ConfirmDialog.jsx", f"{REMOTE}/dashboard/src/components/ConfirmDialog.jsx"),
]


def main() -> int:
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(HOST, username=USER, password=PWD, timeout=30)
    sftp = c.open_sftp()

    for rel, remote in UPLOADS:
        local = os.path.join(REPO, rel.replace("/", os.sep))
        print(f"upload {rel}")
        sftp.put(local, remote)

    with sftp.open(MAIN, "r") as f:
        main = f.read().decode("utf-8")

    changed = False
    if IMPORT.strip() not in main:
        main = main.replace(
            "import TeleAutomationApp from './teleautomation-app.jsx'",
            "import TeleAutomationApp from './teleautomation-app.jsx'\n" + IMPORT,
            1,
        )
        changed = True
        print("Added ConfirmProvider import")

    if NEW_RENDER in main:
        print("ConfirmProvider wrap already present")
    elif OLD_RENDER in main:
        main = main.replace(OLD_RENDER, NEW_RENDER, 1)
        changed = True
        print("Wrapped TeleAutomationApp with ConfirmProvider")
    else:
        print("ERROR: main.jsx render block not found", file=sys.stderr)
        print(main)
        sftp.close()
        c.close()
        return 1

    if changed:
        with sftp.open(MAIN, "w") as f:
            f.write(main.encode("utf-8"))

    sftp.close()

    _, o, _ = c.exec_command(f"cd {REMOTE}/dashboard && npm run build 2>&1 | tail -14", timeout=600)
    print(o.read().decode("utf-8", errors="replace"))

    _, o, _ = c.exec_command(f"grep -o 'index-[^.]*.js' {REMOTE}/static/index.html", timeout=30)
    print("bundle:", o.read().decode().strip())

    c.close()
    print("Done — hard refresh (unregister SW if still blank)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
