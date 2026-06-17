"""Re-sync Pradeep Gupta inbox thread on account9 from Telegram (uid 6300690917)."""
from __future__ import annotations

import os
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HOST = "187.127.169.159"
REMOTE = "/opt/telegramforward"
PY = f"{REMOTE}/venv/bin/python"
SLOT = "account9"
USER_ID = 6300690917


def main() -> int:
    pwd = os.environ.get("VPS_PASSWORD", "")
    if not pwd:
        print("VPS_PASSWORD not set", file=sys.stderr)
        return 1

    import paramiko

    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(HOST, username="root", password=pwd, timeout=30)

    probe = f"""cd {REMOTE} && PYTHONPATH={REMOTE} {PY} <<'PYEOF'
import json
import os
import urllib.request
from http.cookiejar import CookieJar
from urllib.request import HTTPCookieProcessor, build_opener

from core.dm_store import load_inbox

slot = "{SLOT}"
uid = {USER_ID}
before = (load_inbox(slot).get("conversations") or {{}}).get(str(uid))
print("BEFORE", "found" if before else "missing", "msgs", len((before or {{}}).get("messages") or []))

jar = CookieJar()
opener = build_opener(HTTPCookieProcessor(jar))
user = os.environ.get("DASHBOARD_USERNAME", "admin")
password = os.environ.get("DASHBOARD_PASSWORD", "")
login_body = json.dumps({{"username": user, "password": password}}).encode("utf-8")
login_req = urllib.request.Request(
    "http://127.0.0.1:8000/auth/login",
    data=login_body,
    headers={{"Content-Type": "application/json"}},
    method="POST",
)
try:
    opener.open(login_req, timeout=30)
except Exception as e:
    print("LOGIN_ERROR", e)

sync_req = urllib.request.Request(
    f"http://127.0.0.1:8000/inbox/{{slot}}/sync/{{uid}}",
    method="POST",
)
try:
    with opener.open(sync_req, timeout=120) as resp:
        body = json.loads(resp.read().decode("utf-8", errors="replace"))
    print("SYNC_STATUS", body.get("status"), "added", body.get("added"))
except Exception as e:
    print("SYNC_ERROR", e)

after = (load_inbox(slot).get("conversations") or {{}}).get(str(uid)) or {{}}
print("AFTER", after.get("name"), "msgs", len(after.get("messages") or []))
PYEOF
"""
    cmd = f"set -a && . {REMOTE}/.env && set +a && {probe}"
    _, o, e = client.exec_command(cmd, timeout=180)
    out = (o.read() + e.read()).decode("utf-8", errors="replace")
    print(out)
    client.close()
    ok = "AFTER" in out and "SYNC_ERROR" not in out and "msgs 0" not in out.split("AFTER")[-1]
    if "AFTER" in out and "msgs 0" in out.split("AFTER")[-1] and "SYNC_STATUS" in out:
        # sync ran but thread still empty — may be deleted on Telegram side
        ok = "SYNC_STATUS" in out and "error" not in out.lower()
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
