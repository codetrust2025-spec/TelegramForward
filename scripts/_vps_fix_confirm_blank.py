"""Patch app bundle useConfirm (eo) to read global __TA_CONFIRM_VALUE__."""
from __future__ import annotations

import os
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import paramiko

HOST, USER, REMOTE = "187.127.169.159", "root", "/opt/telegramforward"
PWD = os.environ.get("VPS_PASSWORD", "")
REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def main() -> int:
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(HOST, username=USER, password=PWD, timeout=30)
    sftp = c.open_sftp()

    for rel in (
        "scripts/_patch_confirm.js",
        "dashboard/src/context/ConfirmContext.jsx",
        "dashboard/vite.config.js",
    ):
        local = os.path.join(REPO, rel.replace("/", os.sep))
        remote = f"{REMOTE}/{rel}"
        print("upload", rel)
        sftp.put(local, remote)

    sftp.close()

    cmds = [
        f"cd {REMOTE} && node scripts/_patch_confirm.js",
        r"""node -e "
const fs=require('fs');
const html=fs.readFileSync('/opt/telegramforward/static/index.html','utf8');
const m=html.match(/assets\/(app-[^\"]+\.js)/);
const t=fs.readFileSync('/opt/telegramforward/static/assets/'+m[1],'utf8');
const i=t.indexOf('function eo()');
console.log(t.slice(i,i+200));
console.log('ok', t.slice(i,i+200).includes('__TA_CONFIRM_VALUE__'));
" """,
    ]
    for cmd in cmds:
        print(">>>", cmd[:90])
        _, o, e = c.exec_command(cmd, timeout=60)
        print(o.read().decode("utf-8", errors="replace"))
        err = e.read().decode("utf-8", errors="replace")
        if err.strip():
            print("ERR:", err[:400])

    c.close()
    print("Done — hard refresh (Ctrl+Shift+R)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
