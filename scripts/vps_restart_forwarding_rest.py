#!/usr/bin/env python3
"""Restart forwarding accounts so new FORWARD_REST window applies immediately."""
from __future__ import annotations

import json
import socket
import sys
import time

import paramiko

HOST = "187.127.169.159"
USER = "root"
PASSWORD = "8897870998s@SS"
ROOT = "/opt/telegramforward.old"
FORWARDING_SLOTS = ["account1", "account2", "account4", "account6", "account9"]

REMOTE_SCRIPT = r'''
import json, os, sys, time, urllib.error, urllib.request
import http.cookiejar
from pathlib import Path

for line in Path(".env").read_text().splitlines():
    if "=" in line and not line.strip().startswith("#"):
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))

pw = os.environ.get("DASHBOARD_PASSWORD", "")
user = os.environ.get("DASHBOARD_USERNAME", "admin")
slots = json.loads(os.environ.get("RESTART_SLOTS", "[]"))

class Client:
    def __init__(self):
        self.cj = http.cookiejar.CookieJar()
        self.opener = urllib.request.build_opener(
            urllib.request.HTTPCookieProcessor(self.cj)
        )

    def call(self, method, path, body=None):
        data = json.dumps(body).encode() if body is not None else None
        req = urllib.request.Request(
            f"http://127.0.0.1:8000{path}",
            data=data,
            headers={"Content-Type": "application/json"} if data else {},
            method=method,
        )
        try:
            with self.opener.open(req, timeout=30) as r:
                raw = r.read().decode("utf-8", errors="replace")
                return json.loads(raw) if raw.strip() else {}
        except urllib.error.HTTPError as e:
            raw = e.read().decode("utf-8", errors="replace")
            try:
                out = json.loads(raw) if raw.strip() else {"detail": str(e)}
            except json.JSONDecodeError:
                out = {"detail": raw or str(e)}
            out["http_status"] = e.code
            return out

api = Client()
login = api.call("POST", "/auth/login", {"username": user, "password": pw})
if not (login.get("status") == "ok" or login.get("username")):
    print("LOGIN FAILED:", login, file=sys.stderr)
    sys.exit(1)
print("LOGIN ok")

for slot in slots:
    stop = api.call("POST", f"/account/{slot}/stop")
    print(f"STOP {slot}:", json.dumps(stop, ensure_ascii=False))
    time.sleep(2)
    start = api.call("POST", f"/account/{slot}/start?feature=forwarding")
    print(f"START {slot}:", json.dumps(start, ensure_ascii=False))
    time.sleep(3)

state = api.call("GET", "/state")
st = state.get("account_states") or {}
print("\nForwarding rest timers after restart:")
mins = []
for slot in slots:
    a = st.get(slot) or {}
    n = int(a.get("next_cycle_in") or 0)
    print(f"  {slot}: status={a.get('status')} running={a.get('running')} next_cycle_in={n}s ({n//60}m {n%60:02d}s)")
    if n > 0:
        mins.append((n, slot))
if mins:
    m = min(mins)
    print(f"Fleet sleeping ~ {m[0]//60}m {m[0]%60:02d}s (shortest on {m[1]})")
else:
    print("No rest countdown yet (may be posting or starting up)")
'''


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sock = socket.create_connection((HOST, 22), timeout=30)
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(hostname=HOST, username=USER, password=PASSWORD, sock=sock)

    env_export = f"export RESTART_SLOTS='{json.dumps(FORWARDING_SLOTS)}'"
    cmd = (
        f"cd '{ROOT}' && set -a && . ./.env && set +a && "
        f"{env_export} && PYTHONPATH=. ./venv/bin/python - <<'PY'\n{REMOTE_SCRIPT}\nPY"
    )
    _, stdout, stderr = client.exec_command(cmd, timeout=300)
    out = stdout.read().decode("utf-8", errors="replace")
    err = stderr.read().decode("utf-8", errors="replace")
    print(out)
    if err.strip():
        print(err, file=sys.stderr)
    code = stdout.channel.recv_exit_status()
    client.close()
    if code != 0:
        raise SystemExit(code)
    print("\nDone — forwarding accounts restarted with 8–20 min rest window.")


if __name__ == "__main__":
    main()
