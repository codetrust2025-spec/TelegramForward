"""Fix ReferenceError: st is not defined in postingModeConfig prop."""
from __future__ import annotations

import os
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
import paramiko

REMOTE = "/opt/telegramforward"
PWD = os.environ.get("VPS_PASSWORD", "")

BAD = (
    "postingModeConfig={((pm=e.posting_modes)==null?void 0:pm[O])||"
    "((st=e.account_states)==null?void 0:(st[O]||{}).posting_mode_config)}"
)
GOOD = (
    "postingModeConfig={((pm=e.posting_modes)==null?void 0:pm[O])||"
    "((acctSt=e.account_states)==null?void 0:(acctSt[O]||{}).posting_mode_config)}"
)

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
        if BAD in text:
            text = text.replace(BAD, GOOD, 1)
            with sftp.open(path, "w") as f:
                f.write(text.encode("utf-8"))
            print(f"fixed {path}")
        elif GOOD in text:
            print(f"already ok {path}")
        elif "st=e.account_states" in text:
            text = text.replace(
                "((st=e.account_states)==null?void 0:(st[O]||{}).posting_mode_config)",
                "((acctSt=e.account_states)==null?void 0:(acctSt[O]||{}).posting_mode_config)",
            )
            with sftp.open(path, "w") as f:
                f.write(text.encode("utf-8"))
            print(f"fixed alt pattern {path}")
    except OSError as e:
        print(f"skip {path}: {e}")

sftp.close()

_, o, _ = c.exec_command(f"cd {REMOTE}/dashboard && npm run build 2>&1 | tail -14", timeout=600)
print(o.read().decode("utf-8", errors="replace"))

_, o, _ = c.exec_command(
    f"JS=$(grep -o 'app-[^.]*.js' {REMOTE}/static/index.html) && "
    f"grep -c 'acctSt=e.account_states' {REMOTE}/static/assets/$JS && "
    f"grep -c 'st=e.account_states' {REMOTE}/static/assets/$JS || true && "
    f"echo bundle=$JS",
    timeout=60,
)
print(o.read().decode())

# re-apply confirm patch on new bundle
_, o, _ = c.exec_command(f"cd {REMOTE} && node scripts/_patch_confirm.js 2>&1", timeout=60)
print(o.read().decode())

c.close()
print("Done — hard refresh")
