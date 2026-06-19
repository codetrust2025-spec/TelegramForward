#!/usr/bin/env python3
"""Download production candidates.json into local data/ for dev Daily ops."""

from __future__ import annotations

import json
import os
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

DATA_FILE = os.path.join(ROOT, "data", "candidates.json")
HOST = "187.127.169.159"
REMOTE_PATHS = (
    "/opt/telegramforward/data/candidates.json",
    "/opt/telegramforward.old/data/candidates.json",
    "/opt/telegramforward.old/backups/pre_update_20260611_134335/data/candidates.json",
)


def _load_dotenv() -> None:
    env_path = os.path.join(ROOT, ".env")
    if not os.path.isfile(env_path):
        return
    with open(env_path, encoding="utf-8") as f:
        for raw in f:
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, val = line.partition("=")
            key = key.strip()
            if key and key not in os.environ:
                os.environ[key] = val.strip().strip('"').strip("'")


def _validate_payload(data: dict) -> int:
    rows = data.get("candidates")
    if not isinstance(rows, list):
        raise ValueError("Invalid candidates payload — missing candidates list")
    return len(rows)


def fetch_via_vps() -> dict | None:
    password = (os.environ.get("VPS_PASSWORD") or "").strip()
    if not password:
        return None
    try:
        import paramiko
    except ImportError:
        print("paramiko not installed — run: pip install paramiko", file=sys.stderr)
        return None

    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(HOST, username="root", password=password, timeout=30)
    sftp = client.open_sftp()
    try:
        for remote in REMOTE_PATHS:
            try:
                with tempfile.NamedTemporaryFile(delete=False, suffix=".json") as tmp:
                    local = tmp.name
                sftp.get(remote, local)
                with open(local, encoding="utf-8") as f:
                    data = json.load(f)
                os.unlink(local)
                count = _validate_payload(data)
                if count > 0:
                    print(f"Fetched {count} candidates from VPS {remote}")
                    return data
                print(f"Skip empty file: {remote}")
            except OSError:
                continue
    finally:
        sftp.close()
        client.close()
    return None


def fetch_via_production_api() -> dict | None:
    import urllib.error
    import urllib.request

    base = (os.environ.get("PRODUCTION_URL") or "https://teleautomation.online").rstrip("/")
    username = (os.environ.get("DASHBOARD_USERNAME") or "admin").strip()
    password = (os.environ.get("DASHBOARD_PASSWORD") or "").strip()
    if not password:
        return None

    login_body = json.dumps({"username": username, "password": password}).encode("utf-8")
    jar = {}
    req = urllib.request.Request(
        f"{base}/auth/login",
        data=login_body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            cookies = resp.headers.get("Set-Cookie") or ""
            if cookies:
                jar["Cookie"] = cookies.split(";")[0]
    except urllib.error.HTTPError as exc:
        print(f"Production login failed: HTTP {exc.code}", file=sys.stderr)
        return None

    headers = {"Accept": "application/json", **jar}
    req = urllib.request.Request(f"{base}/candidates?month=all", headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        print(f"Production /candidates failed: HTTP {exc.code}", file=sys.stderr)
        return None

    if payload.get("status") != "ok":
        print(payload.get("message") or "Unexpected API response", file=sys.stderr)
        return None
    rows = payload.get("candidates") or []
    if not rows:
        return None
    print(f"Fetched {len(rows)} candidates from {base}/candidates")
    return {"candidates": rows, "updated_at": payload.get("updated_at")}


def save(data: dict) -> str:
    os.makedirs(os.path.dirname(DATA_FILE), exist_ok=True)
    tmp = DATA_FILE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp, DATA_FILE)
    return DATA_FILE


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    _load_dotenv()

    data = fetch_via_vps()
    if data is None:
        data = fetch_via_production_api()
    if data is None:
        print(
            "Could not fetch candidates. Set VPS_PASSWORD for SFTP, or "
            "DASHBOARD_PASSWORD (+ optional PRODUCTION_URL) for HTTPS export.",
            file=sys.stderr,
        )
        return 1

    path = save(data)
    count = _validate_payload(data)
    print(f"Saved {count} candidates to {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
