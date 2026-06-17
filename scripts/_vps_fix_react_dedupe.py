"""Fix duplicate React contexts (useConfirm / ConfirmProvider mismatch)."""
from __future__ import annotations

import os
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import paramiko

HOST, USER, REMOTE = "187.127.169.159", "root", "/opt/telegramforward"
PWD = os.environ.get("VPS_PASSWORD", "")
REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

TA = f"{REMOTE}/dashboard/src/teleautomation-app.jsx"
MAIN = f"{REMOTE}/dashboard/src/main.jsx"
VITE = f"{REMOTE}/dashboard/vite.config.js"

CONFIRM_IMPORT = "import { ConfirmProvider } from './context/ConfirmContext.jsx'\n"

MAIN_OLD = """createRoot(document.getElementById('root')).render(
  <StrictMode>
    <ConfirmProvider>
      <TeleAutomationApp />
    </ConfirmProvider>
  </StrictMode>,
)"""

MAIN_NEW = """createRoot(document.getElementById('root')).render(
  <StrictMode>
    <TeleAutomationApp />
  </StrictMode>,
)"""

EXPORT_OLD = """export default function TeleAutomationApp() {
  return <_Component46><SR /></_Component46>
}"""

EXPORT_NEW = """export default function TeleAutomationApp() {
  return (
    <ConfirmProvider>
      <_Component46>
        <SR />
      </_Component46>
    </ConfirmProvider>
  )
}"""


def patch_vite(text: str) -> tuple[str, bool]:
    if "dedupe: ['react', 'react-dom']" in text or 'dedupe: ["react", "react-dom"]' in text:
        return text, False
    needle = "export default defineConfig({\n  plugins: [react()],"
    insert = needle + "\n  resolve: {\n    dedupe: ['react', 'react-dom'],\n  },"
    if needle not in text:
        raise RuntimeError("vite.config.js pattern not found")
    return text.replace(needle, insert, 1), True


def main() -> int:
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(HOST, username=USER, password=PWD, timeout=30)
    sftp = c.open_sftp()

    local_vite = os.path.join(REPO, "dashboard", "vite.config.js")
    sftp.put(local_vite, VITE)
    print("uploaded vite.config.js (react dedupe)")

    for rel, remote in (
        ("dashboard/src/context/ConfirmContext.jsx", f"{REMOTE}/dashboard/src/context/ConfirmContext.jsx"),
        ("dashboard/src/components/ConfirmDialog.jsx", f"{REMOTE}/dashboard/src/components/ConfirmDialog.jsx"),
    ):
        sftp.put(os.path.join(REPO, rel.replace("/", os.sep)), remote)

    with sftp.open(TA, "r") as f:
        ta = f.read().decode("utf-8")

    ta_changed = False
    if CONFIRM_IMPORT.strip() not in ta:
        ta = ta.replace(
            "import { PostingModePanel } from './components/PostingModePanel.jsx'\n",
            "import { PostingModePanel } from './components/PostingModePanel.jsx'\n" + CONFIRM_IMPORT,
            1,
        )
        ta_changed = True
        print("Added ConfirmProvider import to teleautomation-app.jsx")

    if EXPORT_NEW.strip() in ta:
        print("teleautomation-app ConfirmProvider wrap OK")
    elif EXPORT_OLD in ta:
        ta = ta.replace(EXPORT_OLD, EXPORT_NEW, 1)
        ta_changed = True
        print("Wrapped TeleAutomationApp with ConfirmProvider (same module graph)")
    else:
        print("WARN: TeleAutomationApp export block not matched", file=sys.stderr)

    if ta_changed:
        with sftp.open(TA, "w") as f:
            f.write(ta.encode("utf-8"))

    with sftp.open(MAIN, "r") as f:
        main = f.read().decode("utf-8")

    main_changed = False
    if MAIN_OLD in main:
        main = main.replace(MAIN_OLD, MAIN_NEW, 1)
        main_changed = True
        print("Removed ConfirmProvider from main.jsx (avoid double wrap)")
    if "ConfirmProvider" in main and "import { ConfirmProvider }" in main:
        main = main.replace("import { ConfirmProvider } from './context/ConfirmContext.jsx'\n", "")
        main_changed = True
    if main_changed:
        with sftp.open(MAIN, "w") as f:
            f.write(main.encode("utf-8"))

    sftp.close()

    _, o, _ = c.exec_command(
        f"cd {REMOTE}/dashboard && npm run build 2>&1 | tail -16",
        timeout=600,
    )
    print(o.read().decode("utf-8", errors="replace"))

    _, o, _ = c.exec_command(
        f"JS=$(grep -o 'index-[^.]*.js' {REMOTE}/static/index.html) && "
        f"node -e 'const fs=require(\"fs\");const p=\"{REMOTE}/static/assets/\"+process.argv[1];"
        "const t=fs.readFileSync(p,\"utf8\");"
        "console.log(\"contexts\",(t.match(/createContext\\(null\\)/g)||[]).length);"
        "console.log(t.slice(-420));' \"$JS\"",
        timeout=60,
    )
    print(o.read().decode("utf-8", errors="replace"))

    c.close()
    print("Done — hard refresh; unregister service worker if needed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
