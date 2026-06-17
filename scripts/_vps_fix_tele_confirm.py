"""Ensure ConfirmProvider wrap + patch inline useConfirm on VPS teleautomation-app."""
from __future__ import annotations

import os
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import paramiko

HOST, USER, REMOTE = "187.127.169.159", "root", "/opt/telegramforward"
PWD = os.environ.get("VPS_PASSWORD", "")
REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

EXPORT_OK = """export default function TeleAutomationApp() {
  return (
    <ConfirmProvider>
      <_Component46>
        <SR />
      </_Component46>
    </ConfirmProvider>
  )
}"""


def main() -> int:
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(HOST, username=USER, password=PWD, timeout=30)
    sftp = c.open_sftp()

    for rel in (
        "dashboard/src/context/ConfirmContext.jsx",
        "dashboard/vite.config.js",
        "scripts/_patch_confirm.js",
    ):
        sftp.put(os.path.join(REPO, rel.replace("/", os.sep)), f"{REMOTE}/{rel}")

    ta = f"{REMOTE}/dashboard/src/teleautomation-app.jsx"
    with sftp.open(ta, "r") as f:
        text = f.read().decode("utf-8")

    imp = "import { ConfirmProvider } from './context/ConfirmContext.jsx'\n"
    if imp.strip() not in text:
        text = text.replace(
            "import { PostingModePanel } from './components/PostingModePanel.jsx'\n",
            "import { PostingModePanel } from './components/PostingModePanel.jsx'\n" + imp,
            1,
        )

    # Fix inline hook: allow global fallback (source-level, survives rebuild)
    old_hook = (
        'function to() {\n'
        '  const ctx = w.useContext(Ck);\n'
        '  if (!ctx) {\n'
        '    throw new Error("useConfirm must be used within ConfirmProvider");\n'
        '  }\n'
        '  return ctx;\n'
        '}'
    )
    new_hook = (
        'function to() {\n'
        '  const ctx = w.useContext(Ck) || (typeof globalThis !== "undefined" && globalThis.__TA_CONFIRM_VALUE__) || null;\n'
        '  if (!ctx) {\n'
        '    throw new Error("useConfirm must be used within ConfirmProvider");\n'
        '  }\n'
        '  return ctx;\n'
        '}'
    )
    # Minified-style variants in source
    for old, new in [
        (old_hook, new_hook),
        (
            'function to(){const e=w.useContext(Ck);if(!e)throw new Error("useConfirm must be used within ConfirmProvider");return e}',
            'function to(){const e=w.useContext(Ck)||(typeof globalThis!="undefined"&&globalThis.__TA_CONFIRM_VALUE__)||null;if(!e)throw new Error("useConfirm must be used within ConfirmProvider");return e}',
        ),
        (
            'function to(){const e=k.useContext(Ck);if(!e)throw new Error("useConfirm must be used within ConfirmProvider");return e}',
            'function to(){const e=k.useContext(Ck)||(typeof globalThis!="undefined"&&globalThis.__TA_CONFIRM_VALUE__)||null;if(!e)throw new Error("useConfirm must be used within ConfirmProvider");return e}',
        ),
    ]:
        if old in text:
            text = text.replace(old, new, 1)
            print("patched inline to() in source")

    import re

    if "ConfirmProvider>" not in text or "<ConfirmProvider>" not in text:
        # Replace only the default export at file end (avoid matching nested functions).
        new_text, n = re.subn(
            r"export default function TeleAutomationApp\(\) \{\s*return\s*[^;]+;\s*\}\s*$",
            EXPORT_OK,
            text,
            count=1,
        )
        if n:
            text = new_text
            print("set TeleAutomationApp ConfirmProvider wrap")
        else:
            print("WARN: could not replace TeleAutomationApp export", file=sys.stderr)

    with sftp.open(ta, "w") as f:
        f.write(text.encode("utf-8"))

    sftp.close()

    for cmd in [
        f"cd {REMOTE}/dashboard && npm run build 2>&1 | tail -12",
        f"cd {REMOTE} && node scripts/_patch_confirm.js",
        f"grep -o 'app-[^.]*.js' {REMOTE}/static/index.html",
    ]:
        print(">>>", cmd[:80])
        _, o, e = c.exec_command(cmd, timeout=600)
        print(o.read().decode("utf-8", errors="replace")[:2000])
        err = e.read().decode("utf-8", errors="replace").strip()
        if err:
            print("stderr:", err[:300])

    c.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
