#!/usr/bin/env python3
"""Diagnose fleet (running vs session errors) and restart forward + campaign workers."""
from __future__ import annotations

import json
import os
import socket
import sys
import textwrap
import time

import paramiko

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HOST = "187.127.169.159"
USER = "root"
PASSWORD = os.environ.get("VPS_PASSWORD", "")
REMOTE = "/opt/telegramforward.old"

FORWARD_SLOTS = ["account1", "account2", "account4", "account6", "account9"]
CAMPAIGN_SLOTS = ["account3", "account5", "account7", "account8", "account10"]
ACTIVE = FORWARD_SLOTS + CAMPAIGN_SLOTS

REMOTE_PY = textwrap.dedent(
    f"""
    import json, time, subprocess, urllib.request, urllib.error
    from pathlib import Path

    sys_path = "{REMOTE}"
    import sys
    sys.path.insert(0, sys_path)

    from core.dashboard_auth_vps import get_credentials, create_session_token, SESSION_COOKIE
    from core.posting_mode import load_posting_mode
    from core.account_info_store import load_account_info
    from core.worker_persistence import load_running_slots
    from core.daily_stats import compute_daily_stats

    FORWARD = {FORWARD_SLOTS!r}
    CAMPAIGN = {CAMPAIGN_SLOTS!r}
    ACTIVE = {ACTIVE!r}

    user, pw = get_credentials()
    token = create_session_token(user, role="admin")

    def api(method, path, timeout=45):
        req = urllib.request.Request(
            "http://127.0.0.1:8000" + path,
            method=method,
            data=b"" if method == "POST" else None,
        )
        req.add_header("Cookie", f"{{SESSION_COOKIE}}={{token}}")
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read().decode())

    def grep_logs(pattern, lines=200):
        cmd = (
            "pm2 logs telegram-backend --lines {{n}} --nostream 2>&1 | grep -iE '{{pat}}' | tail -30"
        ).format(n=lines, pat=pattern)
        r = subprocess.run(["bash", "-lc", cmd], capture_output=True, text=True, timeout=25)
        return [l for l in (r.stdout or "").splitlines() if l.strip()]

    print("=== Fleet diagnosis ===")
    running_slots = set(load_running_slots())
    session_issues = []
    for slot in ACTIVE:
        info = load_account_info(slot) or {{}}
        logged = bool(info.get("phone"))
        pm = load_posting_mode(slot)
        role = "FWD" if slot in FORWARD else "CAMP"
        mode = pm.mode or ("forwarding" if pm.forwarding_enabled else "campaign")
        print(
            f"{{slot}} [{{role}}] logged={{logged}} mode={{mode}} "
            f"was_running={{slot in running_slots}} fwd={{pm.forwarding_enabled}} camp={{pm.campaign_enabled}}"
        )
        if not logged:
            session_issues.append((slot, "not logged in"))

    print("\\n=== Recent session / connection errors (backend log) ===")
    err_lines = grep_logs(
        r"wrong session|connection failed|authkey|session|not logged|disconnect"
    )
    if not err_lines:
        print("(no recent session errors in last 200 log lines)")
    else:
        for line in err_lines[-20:]:
            print(line[:240])
            for slot in ACTIVE:
                if slot in line.lower():
                    session_issues.append((slot, "log error"))

    print("\\n=== Posts today (before restart) ===")
    ds = compute_daily_stats(ACTIVE)
    g = ds.get("global") or {{}}
    print("window", ds.get("window"), "forward", g.get("forward_posts"), "campaign", g.get("campaign_posts"))

    print("\\n=== Restarting accounts ===")
    results = {{}}
    for slot in ACTIVE:
        try:
            api("POST", f"/account/{{slot}}/restart", timeout=90)
            results[slot] = "restarted"
            print(f"  {{slot}}: restarted OK")
        except Exception as exc:
            results[slot] = str(exc)
            print(f"  {{slot}}: restart FAIL — {{exc}}")
        time.sleep(0.8)

    print("\\nWaiting 15s for workers to connect...")
    time.sleep(15)

    print("\\n=== Worker state after restart ===")
    running_after = set(load_running_slots())
    for slot in ACTIVE:
        print(f"  {{slot}}: persisted_running={{slot in running_after}}")

    print("\\n=== Recent forward/tick log lines ===")
    tick_lines = grep_logs(r"account[0-9]+.*(forward|tick|sent|Connection|session|Cycle started)", 300)
    for line in tick_lines[-25:]:
        print(line[:240])

    print("\\n=== Posts today (after restart) ===")
    ds2 = compute_daily_stats(ACTIVE)
    g2 = ds2.get("global") or {{}}
    print("forward", g2.get("forward_posts"), "campaign", g2.get("campaign_posts"))

    if session_issues:
        print("\\n=== Accounts needing re-login (manual) ===")
        seen = set()
        for slot, reason in session_issues:
            key = (slot, reason)
            if key in seen:
                continue
            seen.add(key)
            print(f"  {{slot}} — {{reason}}")
    """
)


def connect() -> paramiko.SSHClient:
    sock = socket.create_connection((HOST, 22), timeout=30)
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(HOST, username=USER, password=PASSWORD, sock=sock)
    return c


def main() -> None:
    c = connect()
    cmd = (
        f"cd {REMOTE} && source venv/bin/activate && python3 << 'PYEOF'\n"
        f"{REMOTE_PY}\nPYEOF"
    )
    _, stdout, stderr = c.exec_command(cmd, timeout=300)
    out = stdout.read().decode("utf-8", errors="replace")
    err = stderr.read().decode("utf-8", errors="replace")
    print(out)
    if err.strip():
        print("STDERR:", err, file=sys.stderr)
    c.close()


if __name__ == "__main__":
    main()
