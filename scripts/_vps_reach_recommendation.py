"""Live recommendation: campaign vs forwarding for highest posts."""
from __future__ import annotations

import json
import os
import sys

import paramiko

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HOST, USER = "187.127.169.159", "root"
REMOTE_PY = "/opt/telegramforward/venv/bin/python"
REMOTE = "/opt/telegramforward"


def main() -> int:
    pwd = os.environ.get("VPS_PASSWORD", "")
    if not pwd:
        print("VPS_PASSWORD not set", file=sys.stderr)
        return 1

    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(HOST, username=USER, password=pwd, timeout=30)

    _, o, _ = c.exec_command("curl -s http://127.0.0.1:8000/state", timeout=45)
    state = json.loads(o.read().decode())

    meta_cmd = rf"""
PYTHONPATH={REMOTE} {REMOTE_PY} <<'PY'
import json, os
from core.config import ACCOUNT_SLOTS
from core.account_info_store import load_account_info
from core.posting_mode import load_posting_mode
from core.account_shutdown import is_shutdown_active

def count_lines(path):
    if not os.path.isfile(path):
        return 0
    with open(path, encoding="utf-8", errors="ignore") as f:
        return sum(1 for ln in f if ln.strip())

def joined_count(slot):
    for base in ("/opt/telegramforward", "/opt/telegramforward.old"):
        p = f"{{base}}/data/accounts/{{slot}}/joined_forward_targets.json"
        if not os.path.isfile(p):
            continue
        try:
            with open(p, encoding="utf-8") as f:
                d = json.load(f)
            t = d.get("targets") or d.get("groups") or d
            if isinstance(t, list):
                return len(t)
        except Exception:
            pass
    return 0

rows = []
for slot in ACCOUNT_SLOTS:
    info = load_account_info(slot) or {{}}
    if not (info.get("phone") or info.get("user_id")):
        continue
    pm = load_posting_mode(slot)
    master = count_lines(f"/opt/telegramforward/data/accounts/{{slot}}/groups.txt")
    rows.append({{
        "slot": slot,
        "name": info.get("name") or "?",
        "campaign_on": pm.campaign_enabled,
        "forwarding_on": pm.forwarding_enabled,
        "master_groups": master,
        "joined": joined_count(slot),
        "shutdown": is_shutdown_active(slot),
    }})
print(json.dumps(rows))
PY
"""
    _, o2, _ = c.exec_command(meta_cmd, timeout=60)
    meta = {r["slot"]: r for r in json.loads(o2.read().decode() or "[]")}

    account_states = state.get("account_states") or {}
    account_info = state.get("account_info") or {}
    daily = (state.get("daily_stats") or {}).get("per_account") or {}

    print("=== LIVE ACCOUNTS (logged in) ===\n")
    active = []
    for slot in sorted(meta.keys()):
        m = meta[slot]
        st = account_states.get(slot) or {}
        info = account_info.get(slot) or {}
        d = daily.get(slot) or {}
        camp_run = st.get("campaign_running") or (st.get("campaign") or {}).get("running")
        fwd_run = st.get("forwarding_running") or (st.get("forwarding") or {}).get("running")
        running = bool(camp_run or fwd_run or st.get("running"))
        fwd_today = int(d.get("forward_posts") or d.get("forwarded") or 0)
        camp_today = int(d.get("campaign_posts") or d.get("messages_sent") or 0)
        fwd_tick = int((st.get("forwarding") or {}).get("success") or st.get("forwarding_success") or 0)
        joined = int(m.get("joined") or 0)
        master = int(m.get("master_groups") or 0)
        row = {
            "slot": slot,
            "name": (m.get("name") or info.get("name") or slot)[:32],
            "running": running,
            "shutdown": m.get("shutdown"),
            "fwd_on": m.get("forwarding_on"),
            "camp_on": m.get("campaign_on"),
            "joined": joined,
            "master": master,
            "fwd_today": fwd_today,
            "camp_today": camp_today,
            "fwd_tick": fwd_tick,
        }
        active.append(row)
        status = "RUNNING" if running else ("ready" if not m.get("shutdown") else "shutdown")
        print(
            f"{slot:10} {row['name']:32} | {status:8} | joined={joined:5} master={master:4} "
            f"| today fwd={fwd_today:4} camp={camp_today:4} | tick sent={fwd_tick}"
        )

    print("\n=== RECOMMENDATION ===\n")
    not_shutdown = [r for r in active if not r["shutdown"]]
    running_now = [r for r in active if r["running"]]
    all_fwd = all(r["fwd_on"] and not r["camp_on"] for r in active)

    if all_fwd:
        print("All accounts are configured FORWARDING only (campaign off).")

    if running_now:
        print(f"Currently running: {', '.join(r['slot'] for r in running_now)}")
    else:
        print("No account worker running right now in /state.")

    print(f"Not on shutdown list (can run): {', '.join(r['slot'] for r in not_shutdown) or 'none'}")

    for r in not_shutdown:
        joined, master = r["joined"], r["master"]
        if joined >= 500:
            rec = "KEEP Forwarding — large joined pool; best posts/day"
        elif joined >= 150 and master < joined:
            rec = "KEEP Forwarding — joined inventory beats master list"
        elif master >= 200 and joined < 80:
            rec = "Switch to Campaign — big master list, few joined groups"
        elif joined < 80 and master < 100:
            rec = "Campaign — grow + post master list; forwarding pool too small"
        else:
            rec = "Forwarding if joined≥150, else Campaign"
        print(f"  {r['slot']} ({r['name']}): joined={joined}, master={master} → {rec}")

    best_fwd = max(active, key=lambda r: r["fwd_today"])
    print(f"\nHighest posts today (live): {best_fwd['slot']} ({best_fwd['name']}) — {best_fwd['fwd_today']} forward posts")

    c.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
