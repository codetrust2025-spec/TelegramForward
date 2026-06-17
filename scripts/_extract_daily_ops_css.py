"""Extract daily-ops CSS from VPS bundle CSS into dashboard/src/dailyOps.css"""
import os
import re
import sys

import paramiko

HOST = "187.127.169.159"
PWD = os.environ.get("VPS_PASSWORD", "")
REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(REPO, "dashboard", "src", "dailyOps.css")

MARKERS = (
    ".daily-ops-page",
    ".pending-works-strip",
    ".ops-dashboard",
    ".ops-checklist",
    ".ops-dash-",
    ".ops-interview-",
)


def extract_rules(css: str) -> str:
    """Pull rule blocks whose selector contains daily-ops / ops- markers."""
    out: list[str] = []
    # Split on `}` keeping structure — crude but works for minified css too
    i = 0
    while i < len(css):
        j = css.find("{", i)
        if j < 0:
            break
        k = css.find("}", j)
        if k < 0:
            break
        selector = css[i:j].strip()
        body = css[j : k + 1]
        block = selector + body
        if any(m.rstrip("-") in selector for m in MARKERS):
            out.append(block)
        i = k + 1
    return "\n".join(out)


def main() -> None:
    if not PWD:
        print("VPS_PASSWORD required", file=sys.stderr)
        sys.exit(1)

    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(HOST, username="root", password=PWD, timeout=30)

    cmd = r"""python3 <<'PY'
import pathlib
for p in sorted(pathlib.Path('/opt/telegramforward/static/assets').glob('index-*.css')):
    t = p.read_text(encoding='utf-8', errors='replace')
    if 'daily-ops' in t and 'ops-dashboard' in t:
        print(p.name, len(t))
PY"""
    _, stdout, _ = c.exec_command(cmd)
    pick = stdout.read().decode().strip().splitlines()
    if not pick:
        print("No CSS with daily-ops found", file=sys.stderr)
        sys.exit(2)
    css_name = pick[-1].split()[0]
    print("Using", css_name)

    sftp = c.open_sftp()
    local_tmp = os.path.join(REPO, "static", "assets", css_name)
    os.makedirs(os.path.dirname(local_tmp), exist_ok=True)
    sftp.get(f"/opt/telegramforward/static/assets/{css_name}", local_tmp)
    sftp.close()
    c.close()

    css = open(local_tmp, encoding="utf-8", errors="replace").read()
    extracted = extract_rules(css)
    header = "/* Daily ops + interview roster — ported from production CSS */\n"
    with open(OUT, "w", encoding="utf-8", newline="\n") as f:
        f.write(header)
        f.write(extracted)
        f.write("\n")
    print(f"Wrote {OUT} ({len(extracted)} chars from {css_name})")


if __name__ == "__main__":
    main()
