"""Deploy Karthik human_owned resume fix and flush waiting inbox."""
from __future__ import annotations

import json
import os
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HOST = "187.127.169.159"
USER = "root"
REMOTE = "/opt/telegramforward.old"
PASSWORD = os.environ.get("VPS_PASSWORD", "")
REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def main() -> int:
    if not PASSWORD:
        print("VPS_PASSWORD not set", file=sys.stderr)
        return 1

    import paramiko

    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(HOST, username=USER, password=PASSWORD, timeout=30)
    sftp = client.open_sftp()

    local = os.path.join(REPO, "core", "ai_smart_reply.py")
    remote = f"{REMOTE}/core/ai_smart_reply.py"
    print(f"upload {local} -> {remote}")
    sftp.put(local, remote)
    sftp.close()

    # Login + catch-up on live server
    login_py = r'''
import json, urllib.request, http.cookiejar
cj = http.cookiejar.CookieJar()
opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))
login = json.dumps({"username":"admin","password":"734720077743"}).encode()
req = urllib.request.Request("http://127.0.0.1:8000/auth/login", data=login,
    headers={"Content-Type":"application/json"}, method="POST")
opener.open(req, timeout=30).read()
catch = json.dumps({"max_replies": 20}).encode()
req2 = urllib.request.Request("http://127.0.0.1:8000/ai/smart-reply/catch-up", data=catch,
    headers={"Content-Type":"application/json"}, method="POST")
body = opener.open(req2, timeout=120).read().decode()
print(body)
'''
    remote_login = f"{REMOTE}/scripts/_karthik_catchup_auth_once.py"
    sftp = client.open_sftp()
    with sftp.open(remote_login, "w") as f:
        f.write(login_py)
    sftp.close()

    print(">>> pm2 restart telegram-backend")
    stdin, stdout, stderr = client.exec_command("pm2 restart telegram-backend", timeout=60)
    print(stdout.read().decode("utf-8", errors="replace"))

    import time
    time.sleep(8)

    print(">>> catch-up via authenticated localhost API")
    stdin, stdout, stderr = client.exec_command(
        f"cd {REMOTE} && ./venv/bin/python scripts/_karthik_catchup_auth_once.py",
        timeout=180,
    )
    raw = stdout.read().decode("utf-8", errors="replace")
    try:
        print(json.dumps(json.loads(raw), indent=2)[:4000])
    except json.JSONDecodeError:
        print(raw)

    client.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
