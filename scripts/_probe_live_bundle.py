"""Compare live site bundle vs local build."""
from __future__ import annotations

import os
import re
import sys
import time
import urllib.request

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

BASE = "https://teleautomation.online"


def fetch(url: str) -> str:
    req = urllib.request.Request(url, headers={"Cache-Control": "no-cache"})
    with urllib.request.urlopen(req, timeout=25) as r:
        return r.read().decode("utf-8", errors="replace")


def main() -> int:
    html = fetch(f"{BASE}/?nocache={int(time.time())}")
    app_m = re.search(r"/assets/(app-[^\"']+\.js)", html)
    css_m = re.search(r"/assets/(index-[^\"']+\.css)", html)
    print("LIVE index.html references:")
    print("  js:", app_m.group(1) if app_m else "MISSING")
    print("  css:", css_m.group(1) if css_m else "MISSING")

    local_html = open(
        os.path.join(os.path.dirname(os.path.dirname(__file__)), "static", "index.html"),
        encoding="utf-8",
    ).read()
    local_app = re.search(r"/assets/(app-[^\"']+\.js)", local_html)
    print("LOCAL index.html references:")
    print("  js:", local_app.group(1) if local_app else "MISSING")

    if app_m:
        js_url = f"{BASE}/assets/{app_m.group(1)}?t={int(time.time())}"
        js = urllib.request.urlopen(js_url, timeout=30).read()
        print("LIVE bundle size:", len(js))
        markers = [
            "headerBusy",
            "includeSlot",
            "quickBusy",
            "desk-mode-hint",
            "Start all",
            "Stop all",
        ]
        for m in markers:
            print(f"  contains {m!r}:", m.encode() in js)

    PASSWORD = os.environ.get("VPS_PASSWORD")
    if not PASSWORD:
        return 0

    import paramiko

    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect("187.127.169.159", username="root", password=PASSWORD, timeout=30)
    cmds = [
        "grep -o 'app-[^\"]*\\.js' /opt/telegramforward.old/static/index.html | head -1",
        "grep -o 'app-[^\"]*\\.js' /opt/telegramforward/static/index.html 2>/dev/null | head -1",
        "ls -la /opt/telegramforward/static/assets/app-*.js 2>/dev/null | tail -5",
        "ls -la /opt/telegramforward.old/static/assets/app-*.js 2>/dev/null | tail -5",
    ]
    for cmd in cmds:
        print(">>>", cmd)
        stdin, stdout, stderr = client.exec_command(cmd, timeout=30)
        print(stdout.read().decode("utf-8", errors="replace").strip())
    client.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
