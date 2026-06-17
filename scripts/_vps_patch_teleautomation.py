"""Patch teleautomation-app.jsx to include PostingModePanel."""
from __future__ import annotations

import os
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import paramiko

HOST, USER, REMOTE = "187.127.169.159", "root", "/opt/telegramforward"
PATH = f"{REMOTE}/dashboard/src/teleautomation-app.jsx"
MAIN = f"{REMOTE}/dashboard/src/main.jsx"
INDEX_CSS = f"{REMOTE}/dashboard/src/index.css"
PWD = os.environ.get("VPS_PASSWORD", "")

IMPORT_LINE = (
    "import { PostingModePanel } from './components/PostingModePanel.jsx'\n"
)

OLD_FOOTER = (
    '</footer><div className="acct-v3-message-editor" onClick={N => N.stopPropagation()}>'
    "<_Component7 slot={e}"
)

NEW_FOOTER = (
    '</footer><div className="acct-v3-posting-mode" onClick={N => N.stopPropagation()}>'
    "<PostingModePanel slot={e} postingModeConfig={postingModeConfig} acctRunning={i} "
    "onUpdated={onPostingModeUpdated || T || (() => {})} /></div>"
    "{!isForwardingMode ? <div className=\"acct-v3-message-editor\" onClick={N => N.stopPropagation()}>"
    "<_Component7 slot={e}"
)

OLD_FOOTER_CLOSE = (
    'rewriteMethod={A} /></div></s.Fragment> : L === "idle" ?'
)
NEW_FOOTER_CLOSE = (
    'rewriteMethod={A} /></div> : null}</s.Fragment> : L === "idle" ?'
)

OLD_EK_SIG = "  rewriteMethod: A = \"\",\n  cycle: O = 0\n}) {"
NEW_EK_SIG = (
    "  rewriteMethod: A = \"\",\n  cycle: O = 0,\n"
    "  postingModeConfig,\n  onPostingModeUpdated\n}) {"
)

OLD_EK_PROPS = "rewriteMethod={p} key={O} />}"
NEW_EK_PROPS = (
    "rewriteMethod={p} postingModeConfig={"
    "(e.posting_modes==null?void 0:e.posting_modes[O])||"
    "(e.account_states==null?void 0:(e.account_states[O]||{}).posting_mode_config)} "
    "onPostingModeUpdated={f} key={O} />}"
)

OLD_RETURN_MARKER = "  const ln = [\"account-card\""
NEW_RETURN_MARKER = (
    "  const postingMode = (f == null ? void 0 : f.posting_mode) || "
    "(postingModeConfig == null ? void 0 : postingModeConfig.mode) || \"campaign\";\n"
    "  const isForwardingMode = postingMode === \"forwarding\";\n"
    "  const ln = [\"account-card\""
)


def main() -> int:
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(HOST, username=USER, password=PWD, timeout=30)
    sftp = c.open_sftp()

    with sftp.open(PATH, "r") as f:
        text = f.read().decode("utf-8")

    if "PostingModePanel" in text and "acct-v3-posting-mode" in text:
        print("teleautomation-app.jsx already patched")
    else:
        if IMPORT_LINE.strip() not in text:
            text = text.replace(
                "import { jsx as _jsx",
                IMPORT_LINE + "import { jsx as _jsx",
                1,
            )
        for old, new, label in [
            (OLD_FOOTER, NEW_FOOTER, "footer"),
            (OLD_FOOTER_CLOSE, NEW_FOOTER_CLOSE, "footer-close"),
            (OLD_EK_SIG, NEW_EK_SIG, "ek-sig"),
            (OLD_EK_PROPS, NEW_EK_PROPS, "ek-props"),
            (OLD_RETURN_MARKER, NEW_RETURN_MARKER, "return-marker"),
        ]:
            if old not in text:
                print(f"ERROR: {label} marker not found", file=sys.stderr)
                return 1
            text = text.replace(old, new, 1)
        with sftp.open(PATH, "w") as f:
            f.write(text.encode("utf-8"))
        print("Patched teleautomation-app.jsx")

    # Ensure posting-mode CSS is loaded
    with sftp.open(MAIN, "r") as f:
        main = f.read().decode("utf-8")
    if "index.css" not in main:
        main = main.replace(
            "import './teleautomation.css'",
            "import './teleautomation.css'\nimport './index.css'",
            1,
        )
        with sftp.open(MAIN, "w") as f:
            f.write(main.encode("utf-8"))
        print("Updated main.jsx to import index.css")

    sftp.close()

    for cmd in [
        f"cd {REMOTE}/dashboard && npm run build 2>&1 | tail -15",
        f'grep -c "Posting mode" {REMOTE}/static/assets/*.js',
        f"grep -o 'index-[^.]*.js' {REMOTE}/static/index.html",
    ]:
        print(">>>", cmd)
        _, o, _ = c.exec_command(cmd, timeout=600)
        print(o.read().decode("utf-8", errors="replace"))

    c.close()
    print("Patch deploy complete")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
