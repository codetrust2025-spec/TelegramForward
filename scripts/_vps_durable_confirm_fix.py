"""Rebuild with ConfirmContext fix + patch teleautomation inline provider global."""
from __future__ import annotations

import os
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import paramiko

HOST, USER, REMOTE = "187.127.169.159", "root", "/opt/telegramforward"
PWD = os.environ.get("VPS_PASSWORD", "")
REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

GLOBAL_SET = (
    '  if (typeof globalThis !== "undefined") {\n'
    '    globalThis.__TA_CONFIRM_VALUE__ = { confirm: n };\n'
    '  }\n'
)

OLD_INLINE = """  return <uv.Provider value={{
    confirm: n
  }}>{e}{t && <_k"""

NEW_INLINE = """  if (typeof globalThis !== "undefined") {
    globalThis.__TA_CONFIRM_VALUE__ = { confirm: n };
  }
  return <uv.Provider value={{
    confirm: n
  }}>{e}{t && <_k"""


def main() -> int:
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(HOST, username=USER, password=PWD, timeout=30)
    sftp = c.open_sftp()

    uploads = [
        ("dashboard/src/context/ConfirmContext.jsx", f"{REMOTE}/dashboard/src/context/ConfirmContext.jsx"),
        ("dashboard/vite.config.js", f"{REMOTE}/dashboard/vite.config.js"),
        ("scripts/_patch_confirm.js", f"{REMOTE}/scripts/_patch_confirm.js"),
        ("scripts/production_update.sh", f"{REMOTE}/scripts/production_update.sh"),
    ]
    for rel, remote in uploads:
        sftp.put(os.path.join(REPO, rel.replace("/", os.sep)), remote)
        print("upload", rel)

    ta = f"{REMOTE}/dashboard/src/teleautomation-app.jsx"
    with sftp.open(ta, "r") as f:
        content = f.read().decode("utf-8")

    if "globalThis.__TA_CONFIRM_VALUE__ = { confirm: n }" in content:
        print("teleautomation inline global already set")
    elif OLD_INLINE in content:
        content = content.replace(OLD_INLINE, NEW_INLINE, 1)
        with sftp.open(ta, "w") as f:
            f.write(content.encode("utf-8"))
        print("patched inline _Component45 global")
    else:
        print("WARN: inline ConfirmProvider pattern not found", file=sys.stderr)

    sftp.close()

    cmds = [
        f"cd {REMOTE} && bash scripts/production_update.sh 2>&1 | tail -25",
    ]
    for cmd in cmds:
        print(">>>", cmd[:95])
        _, o, e = c.exec_command(cmd, timeout=600000)
        out = o.read().decode("utf-8", errors="replace")
        print(out[-3000:] if len(out) > 3000 else out)
        err = e.read().decode("utf-8", errors="replace")
        if err.strip():
            print("ERR:", err[-500:])

    _, o, _ = c.exec_command(
        r"""node -e "
const fs=require('fs');
const html=fs.readFileSync('/opt/telegramforward/static/index.html','utf8');
const m=html.match(/assets\/(app-[^\"]+\.js)/);
const t=fs.readFileSync('/opt/telegramforward/static/assets/'+m[1],'utf8');
const i=t.indexOf('function eo()');
console.log('bundle', m[1]);
console.log(t.slice(i,i+200));
console.log('ik clears global on unmount', t.includes('globalThis[rd]===l&&(globalThis[rd]=null)'));
" """,
        timeout=30,
    )
    print(o.read().decode("utf-8", errors="replace"))
    c.close()
    print("Done — hard refresh + unregister service worker if needed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
