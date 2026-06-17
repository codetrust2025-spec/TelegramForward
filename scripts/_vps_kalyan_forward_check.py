"""Check whether account7 (Kalyan) has sent forwarding messages after start."""
from __future__ import annotations

import json
import os
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import paramiko

HOST, USER = "187.127.169.159", "root"
PWD = os.environ.get("VPS_PASSWORD", "")
SLOT = "account7"


def main() -> int:
    if not PWD:
        print("VPS_PASSWORD not set", file=sys.stderr)
        return 1

    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(HOST, username=USER, password=PWD, timeout=30)

    _, o, _ = c.exec_command("curl -s http://127.0.0.1:8000/state", timeout=30)
    state = json.loads(o.read().decode())
    st = (state.get("account_states") or {}).get(SLOT) or {}
    info = (state.get("account_info") or {}).get(SLOT) or {}
    per = (state.get("daily_stats") or {}).get("per_account") or {}
    row = per.get(SLOT) or {}

    print(f"Account: {info.get('name')} ({SLOT})")
    print(f"  running: {st.get('running')}")
    print(f"  posting_mode: {st.get('posting_mode')}")
    print(f"  cycle (tick #): {st.get('cycle')}")
    print(f"  success (sent this tick): {st.get('success')}")
    print(f"  skipped: {st.get('skipped_already_posted')}")
    print(f"  failed: {st.get('failed')}")
    print(f"  active_groups (tick total): {st.get('active_groups')}")
    print(f"  current_group: {st.get('current_group')}")
    print(f"  notification: {st.get('notification')}")
    print(f"  next_cycle_in: {st.get('next_cycle_in')}s")
    print(f"  daily forward_posts: {row.get('forward_posts')}")
    print(f"  daily forwarded (legacy): {row.get('forwarded')}")

    log_cmds = [
        f"tail -60 /opt/telegramforward.old/logs/{SLOT}.log 2>/dev/null",
        f"tail -60 /opt/telegramforward/logs/{SLOT}.log 2>/dev/null",
        "pm2 logs telegramforward --lines 80 --nostream 2>/dev/null | tail -80",
    ]
    for cmd in log_cmds:
        print(f"\n>>> {cmd}")
        _, out, _ = c.exec_command(cmd, timeout=30)
        text = out.read().decode(errors="replace").strip()
        if text:
            lines = [ln for ln in text.splitlines() if "Forward" in ln or "forward" in ln or "tick" in ln.lower()]
            if lines:
                print("\n".join(lines[-25:]))
            else:
                print(text[-2500:])
        else:
            print("(no log)")

    for path in (
        "/opt/telegramforward.old/data/send_stats.json",
        "/opt/telegramforward/data/send_stats.json",
    ):
        print(f"\n>>> {path}")
        _, out, _ = c.exec_command(
            f"test -f {path} && python3 -c \"import json; d=json.load(open('{path}')); "
            f"print(json.dumps(d.get('{SLOT}', {{}}), indent=2)[:2500])\" || echo missing",
            timeout=20,
        )
        print(out.read().decode(errors="replace").strip() or "(empty)")

    c.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
