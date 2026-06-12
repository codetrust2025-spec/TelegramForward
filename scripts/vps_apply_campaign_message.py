#!/usr/bin/env python3
"""Stop fleet, apply campaign message to each account file, restart campaign."""
from __future__ import annotations

import json
import socket
import sys
import time

import paramiko

HOST = "187.127.169.159"
USER = "root"
PASSWORD = "REMOVED_VPS_PASSWORD"

REMOTE = r'''
import json, os, sys, time, urllib.error, urllib.request, http.cookiejar
from pathlib import Path

ROOT = Path("/opt/telegramforward.old")
for line in (ROOT / ".env").read_text().splitlines():
    if "=" in line and not line.strip().startswith("#"):
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))

pw = os.environ.get("DASHBOARD_PASSWORD", "")
user = os.environ.get("DASHBOARD_USERNAME", "admin")
campaign_slots = json.loads(os.environ.get("CAMPAIGN_SLOTS", "[]"))
all_slots = [f"account{i}" for i in range(1, 11)]

class C:
    def __init__(self):
        self.cj = http.cookiejar.CookieJar()
        self.op = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(self.cj))
    def call(self, method, path, body=None):
        data = json.dumps(body).encode() if body is not None else None
        req = urllib.request.Request(
            f"http://127.0.0.1:8000{path}",
            data=data,
            headers={"Content-Type": "application/json"} if data else {},
            method=method,
        )
        with self.op.open(req, timeout=60) as r:
            raw = r.read().decode()
            return json.loads(raw) if raw.strip() else {}

api = C()
api.call("POST", "/auth/login", {"username": user, "password": pw})

# Load saved default text
from core.fleet_defaults import get_fleet_defaults
text = (get_fleet_defaults().get("campaign_message") or "").strip()
print(f"Default message chars: {len(text)}")

print("Stopping all accounts...")
for slot in all_slots:
    api.call("POST", f"/account/{slot}/stop")
    time.sleep(0.5)
time.sleep(3)

print("Applying message to campaign accounts (direct save)...")
from core.message_store import save_message_for_account
for slot in campaign_slots:
    save_message_for_account(slot, text)
    print(f"  wrote {slot}")

# Also run bulk apply now that stopped
apply = api.call("POST", "/fleet/apply-campaign", {"use_saved_default": True, "message": text})
print("APPLY:", json.dumps({k: apply.get(k) for k in ("updated", "skipped_running", "errors", "message_chars")}, ensure_ascii=False))

print("Starting campaign accounts...")
for slot in campaign_slots:
    out = api.call("POST", f"/account/{slot}/start?feature=campaign")
    print(f"  {slot}: {out.get('status')}")
    time.sleep(2)

needle = "From Calls to Offer"
print("\nVERIFY:")
for slot in campaign_slots:
    p = ROOT / "data" / "accounts" / slot / "message.txt"
    t = p.read_text(encoding="utf-8")
    print(f"  {slot}: ok={needle in t}")
'''


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sock = socket.create_connection((HOST, 22), timeout=30)
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(hostname=HOST, username=USER, password=PASSWORD, sock=sock)
    slots = ["account3", "account5", "account7", "account8", "account10"]
    cmd = (
        f"cd /opt/telegramforward.old && set -a && . ./.env && set +a && "
        f"export CAMPAIGN_SLOTS='{json.dumps(slots)}' && "
        f"PYTHONPATH=. ./venv/bin/python - <<'PY'\n{REMOTE}\nPY"
    )
    _, stdout, stderr = client.exec_command(cmd, timeout=300)
    print(stdout.read().decode("utf-8", errors="replace"))
    if stderr.read().decode().strip():
        print("ERR:", stderr.read())
    client.close()


if __name__ == "__main__":
    main()
