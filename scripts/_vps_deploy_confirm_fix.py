"""Deploy global ConfirmContext fallback (duplicate React in teleautomation bundle)."""
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
        "dashboard/src/context/ConfirmContext.jsx",
        "dashboard/vite.config.js",
    ):
        local = os.path.join(REPO, rel.replace("/", os.sep))
        remote = f"{REMOTE}/{rel}"
        print("upload", rel)
        sftp.put(local, remote)

    ta_path = f"{REMOTE}/dashboard/src/teleautomation-app.jsx"
    with sftp.open(ta_path, "r") as f:
        ta = f.read().decode("utf-8")

    needle = 'throw new Error("useConfirm must be used within ConfirmProvider")'
    patch = (
        'e = e || (typeof globalThis !== "undefined" && globalThis.__TA_CONFIRM_VALUE__) || null; '
        'if (!e) throw new Error("useConfirm must be used within ConfirmProvider")'
    )
    # Minified / bundled-style hook bodies (no spaces)
    patch_min = (
        'e=e||typeof globalThis!="undefined"&&globalThis.__TA_CONFIRM_VALUE__||null;'
        'if(!e)throw new Error("useConfirm must be used within ConfirmProvider")'
    )

    ta_changed = False
    if "__TA_CONFIRM_VALUE__" in ta:
        print("teleautomation-app confirm fallback already patched")
    else:
        for old, new in [
            (f"if (!e) {needle}", f"if (!e) {{ {patch} }}"),
            (f"if(!e){needle}", patch_min),
        ]:
            if old in ta:
                ta = ta.replace(old, new, 1)
                ta_changed = True
                print("patched inline useConfirm in teleautomation-app.jsx")
                break
        if not ta_changed and needle in ta:
            print("WARN: useConfirm found but pattern not matched", file=sys.stderr)

    if ta_changed:
        with sftp.open(ta_path, "w") as f:
            f.write(ta.encode("utf-8"))

    sftp.close()

    _, o, _ = c.exec_command(f"cd {REMOTE}/dashboard && npm run build 2>&1 | tail -14", timeout=600)
    print(o.read().decode("utf-8", errors="replace"))

    patch_js = (
        f"cd {REMOTE} && JS=$(grep -o 'index-[^.]*.js' static/index.html) && "
        "node -e \""
        "const fs=require('fs');"
        "const p='static/assets/'+process.argv[1];"
        "let t=fs.readFileSync(p,'utf8');"
        "const badRe=/function to\\(\\)\\{const e=k\\.useContext\\((\\w+)\\);e=e\\|\\|typeof globalThis/g;"
        "const plainRe=/function to\\(\\)\\{const e=k\\.useContext\\((\\w+)\\);if\\(!e\\)throw new Error\\(\\\"useConfirm must be used within ConfirmProvider\\\"\\);return e\\}/;"
        "const mk=(c)=>'function to(){const e=k.useContext('+c+')||(typeof globalThis!=\\\"undefined\\\"&&globalThis.__TA_CONFIRM_VALUE__)||null;if(!e)throw new Error(\\\"useConfirm must be used within ConfirmProvider\\\");return e}';"
        "const broken=/function to\\(\\)\\{const e=k\\.useContext\\(\\)\\|\\|/;"
        "if(broken.test(t)){const ctx=(t.match(/(\\w+)=k\\.createContext\\(null\\);function to\\(\\)/)||[])[1]||'Ok';"
        "t=t.replace(broken,()=>mk(ctx));console.log('fixed empty useContext',ctx);}"
        "else if(badRe.test(t)){t=t.replace(badRe,(m,c)=>mk(c));console.log('fixed bad const reassignment');}"
        "else if(plainRe.test(t) && !t.includes('__TA_CONFIRM_VALUE__||null;if(!e)')){"
        "t=t.replace(plainRe,(m,c)=>mk(c));console.log('applied global fallback');}"
        "else if(t.includes('__TA_CONFIRM_VALUE__') && t.includes('function to()')){console.log('already ok',process.argv[1]);process.exit(0);}"
        "else{console.error('pattern missing');process.exit(1);}"
        "fs.writeFileSync(p,t);"
        "console.log('patched',process.argv[1]);\""
        ' "$JS"'
    )
    _, o, e = c.exec_command(patch_js, timeout=60)
    out = o.read().decode("utf-8", errors="replace")
    err = e.read().decode("utf-8", errors="replace")
    print(out or err)

    c.close()
    print("Done — hard refresh")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
