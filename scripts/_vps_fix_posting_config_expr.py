"""Fix postingModeConfig JSX — no undeclared assignments (st/acctSt)."""
from __future__ import annotations

import os
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
import paramiko

REMOTE = "/opt/telegramforward"
PWD = os.environ.get("VPS_PASSWORD", "")

# Any variant using (var=e.account_states) in postingModeConfig
REPLACEMENTS = [
    (
        "postingModeConfig={((pm=e.posting_modes)==null?void 0:pm[O])||"
        "((st=e.account_states)==null?void 0:(st[O]||{}).posting_mode_config)}",
        "postingModeConfig={((pm=e.posting_modes)==null?void 0:pm[O])||"
        "((e.account_states)==null?void 0:((e.account_states[O]||{}).posting_mode_config))}",
    ),
    (
        "postingModeConfig={((pm=e.posting_modes)==null?void 0:pm[O])||"
        "((acctSt=e.account_states)==null?void 0:(acctSt[O]||{}).posting_mode_config)}",
        "postingModeConfig={((pm=e.posting_modes)==null?void 0:pm[O])||"
        "((e.account_states)==null?void 0:((e.account_states[O]||{}).posting_mode_config))}",
    ),
    (
        "((st=e.account_states)==null?void 0:(st[O]||{}).posting_mode_config)",
        "((e.account_states)==null?void 0:((e.account_states[O]||{}).posting_mode_config))",
    ),
    (
        "((acctSt=e.account_states)==null?void 0:(acctSt[O]||{}).posting_mode_config)",
        "((e.account_states)==null?void 0:((e.account_states[O]||{}).posting_mode_config))",
    ),
]

GOOD = (
    "postingModeConfig={(e.posting_modes==null?void 0:e.posting_modes[O])||"
    "(e.account_states==null?void 0:(e.account_states[O]||{}).posting_mode_config)}"
)
REPLACEMENTS.append(
    (
        "postingModeConfig={((pm=e.posting_modes)==null?void 0:pm[O])||"
        "((e.account_states)==null?void 0:((e.account_states[O]||{}).posting_mode_config))}",
        GOOD,
    )
)


def main() -> int:
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect("187.127.169.159", username="root", password=PWD, timeout=30)
    sftp = c.open_sftp()

    for path in (
        f"{REMOTE}/dashboard/src/teleautomation-app.jsx",
        "/opt/telegramforward.old/dashboard/src/teleautomation-app.jsx",
    ):
        try:
            with sftp.open(path, "r") as f:
                text = f.read().decode("utf-8")
            changed = False
            for old, new in REPLACEMENTS:
                if old in text:
                    text = text.replace(old, new, 1)
                    changed = True
                    print(f"replaced pattern in {path}")
            if GOOD in text and not changed:
                print(f"already ok {path}")
            elif changed:
                with sftp.open(path, "w") as f:
                    f.write(text.encode("utf-8"))
        except OSError as e:
            print(f"skip {path}: {e}")

    sftp.close()

    _, o, _ = c.exec_command(f"cd {REMOTE}/dashboard && npm run build 2>&1 | tail -12", timeout=600)
    print(o.read().decode("utf-8", errors="replace"))

    _, o, _ = c.exec_command(
        f"cd {REMOTE} && node scripts/_patch_confirm.js 2>&1",
        timeout=60,
    )
    print(o.read().decode("utf-8", errors="replace"))

    _, o, _ = c.exec_command(
        f"JS=$(grep -o 'app-[^.]*.js' {REMOTE}/static/index.html) && "
        f"grep -E 'acctSt=|st=e.account_states' {REMOTE}/static/assets/$JS | head -3 || echo 'no bad assigns'; "
        f"echo bundle=$JS",
        timeout=60,
    )
    print(o.read().decode())

    c.close()
    print("Done — hard refresh")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
