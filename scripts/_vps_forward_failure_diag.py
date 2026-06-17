"""Diagnose interval-forward failures across fleet (VPS /state + logs)."""
from __future__ import annotations

import json
import os
import re
import sys
from collections import Counter

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HOST, USER = "187.127.169.159", "root"
PWD = os.environ.get("VPS_PASSWORD", "")
REMOTE = "/opt/telegramforward.old"

FAIL_PATTERNS = [
    ("flood", re.compile(r"flood|FloodWait|wait of \d+ seconds", re.I)),
    ("cant_write", re.compile(r"can't write|write forbidden|ChatWriteForbidden", re.I)),
    ("blocked", re.compile(r"banned|private|restricted|blocked|admin privileges", re.I)),
    ("invalid", re.compile(r"invalid|username|not occupied|ChannelInvalid", re.I)),
    ("peer", re.compile(r"peer|entity|Could not find|No user has", re.I)),
    ("forward_source", re.compile(r"source|forward_messages|message id", re.I)),
    ("session", re.compile(r"disconnect|not connected|database is locked|auth", re.I)),
    ("timeout", re.compile(r"timeout|timed out", re.I)),
]


def classify_line(line: str) -> str:
    for name, rx in FAIL_PATTERNS:
        if rx.search(line):
            return name
    if re.search(r"error|fail|exception", line, re.I):
        return "other_error"
    return ""


def main() -> int:
    if not PWD:
        print("VPS_PASSWORD not set", file=sys.stderr)
        return 1

    import paramiko

    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(HOST, username=USER, password=PWD, timeout=30)

    _, o, _ = c.exec_command("curl -s http://127.0.0.1:8000/state", timeout=45)
    state = json.loads(o.read().decode())
    posting_modes = state.get("posting_modes") or {}
    account_states = state.get("account_states") or {}
    account_info = state.get("account_info") or {}
    daily = (state.get("daily_stats") or {}).get("per_account") or {}

    forwarding_slots = []
    print("=== All logged-in accounts (mode / forward tick) ===")
    for slot in sorted(account_states.keys()):
        if not account_info.get(slot):
            continue
        st = account_states[slot]
        mode = (posting_modes.get(slot) or st.get("posting_mode") or "?").lower()
        fwd = st.get("forwarding") or {}
        sent = int(fwd.get("success") or st.get("forwarding_success") or 0)
        failed = int(fwd.get("failed") or st.get("forwarding_failed") or 0)
        fr = st.get("forwarding_running") or fwd.get("running")
        name = (account_info.get(slot) or {}).get("name") or slot
        print(
            f"  {slot} {name}: mode={mode} fwd_running={fr} "
            f"tick_sent={sent} fail={failed} cycle={st.get('cycle')}"
        )
        if mode in ("forwarding", "both") or fr:
            forwarding_slots.append(slot)

    print("=== Forwarding accounts ===")
    fleet_sent = fleet_fail = fleet_skip = fleet_active = 0
    for slot in forwarding_slots:
        st = account_states[slot]
        fwd = st.get("forwarding") or {}
        sent = int(fwd.get("success") or st.get("forwarding_success") or st.get("success") or 0)
        failed = int(fwd.get("failed") or st.get("forwarding_failed") or 0)
        skipped = int(fwd.get("skipped_already_posted") or st.get("skipped_already_posted") or 0)
        active = int(fwd.get("active_groups") or st.get("active_groups") or 0)
        cycle = int(fwd.get("cycle") or st.get("cycle") or 0)
        tried = sent + failed + skipped
        rate = f"{(100 * sent / tried):.1f}%" if tried else "n/a"
        name = (account_info.get(slot) or {}).get("name") or slot
        row = daily.get(slot) or {}
        fleet_sent += sent
        fleet_fail += failed
        fleet_skip += skipped
        fleet_active += active
        fc = fwd.get("failure_counts") or {}
        fc_s = f" breakdown={dict(sorted(fc.items(), key=lambda x: -x[1])[:5])}" if fc else ""
        print(
            f"  {slot} ({name}): tick#{cycle} sent={sent} fail={failed} skip={skipped} "
            f"tried={tried} success={rate} tick_targets={active} "
            f"forward_posts_since_reset={row.get('forward_posts', 0)} "
            f"status={st.get('status')} next_in={st.get('next_cycle_in')}s "
            f"heavy_rl={st.get('heavy_rate_limit')}{fc_s}"
        )

    ft = fleet_sent + fleet_fail + fleet_skip
    print(
        f"\n=== Fleet tick totals === sent={fleet_sent} failed={fleet_fail} "
        f"skipped={fleet_skip} tried={ft} "
        f"success_rate={(100*fleet_sent/ft):.1f}%" if ft else "\n(no tick data)"
    )

    _, o, _ = c.exec_command(
        f"cat {REMOTE}/data/forward_message_settings.json 2>/dev/null || echo '{{}}'",
        timeout=15,
    )
    print(f"\n=== forward_message_settings.json ===\n{o.read().decode().strip()}")

    _, o, _ = c.exec_command(
        f"test -f {REMOTE}/data/internal/fleet_defaults.yaml && "
        f"grep -E 'forward|rest|batch|join' {REMOTE}/data/internal/fleet_defaults.yaml | head -30 "
        "|| echo '(no fleet_defaults)'",
        timeout=15,
    )
    fd = o.read().decode().strip()
    if fd:
        print(f"\n=== fleet_defaults (forward-related) ===\n{fd}")

    print("\n=== Log failure patterns (last 500 lines per forwarding account) ===")
    total_counts: Counter = Counter()
    for slot in forwarding_slots:
        log_path = f"{REMOTE}/logs/{slot}.log"
        cmd = (
            f"test -f {log_path} && tail -500 {log_path} | "
            f"grep -iE 'fail|error|flood|forbidden|banned|invalid|forward' || true"
        )
        _, out, _ = c.exec_command(cmd, timeout=25)
        lines = [ln for ln in out.read().decode(errors="replace").splitlines() if ln.strip()]
        slot_counts: Counter = Counter()
        for ln in lines:
            cat = classify_line(ln)
            if cat:
                slot_counts[cat] += 1
                total_counts[cat] += 1
        if slot_counts:
            top = ", ".join(f"{k}={v}" for k, v in slot_counts.most_common(6))
            print(f"  {slot}: {top}")
            sample = [ln for ln in lines if classify_line(ln)][:2]
            for s in sample:
                print(f"    · {s[:140]}")
        else:
            print(f"  {slot}: (no classified errors in tail)")

    print("\n=== Fleet log pattern totals ===")
    for k, v in total_counts.most_common():
        print(f"  {k}: {v}")

    # PM2 / structured logs fallback
    _, o, _ = c.exec_command(
        "pm2 logs telegram-backend --lines 200 --nostream 2>/dev/null | "
        "grep -iE 'Forward tick|flood|forbidden|fail' | tail -40 || true",
        timeout=30,
    )
    pm2 = o.read().decode(errors="replace").strip()
    if pm2:
        print("\n=== Recent PM2 forward-related lines ===")
        print(pm2[-3500:])

    c.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
