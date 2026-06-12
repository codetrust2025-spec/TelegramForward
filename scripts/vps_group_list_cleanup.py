#!/usr/bin/env python3
"""
Build and apply cleaned master group list on VPS.
Keeps: posted successfully on any account, or never blocked/invalid.
Removes: blocked/invalid on any account, join_limited-only failures with no success.
Target: ~100-150 groups.
"""
import json
import os
import re
import shutil
import socket
import sys
import time
from datetime import datetime

import paramiko

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
PASSWORD = os.environ.get("VPS_PASSWORD", "")
REMOTE = "/opt/telegramforward.old"

CLEANUP_SCRIPT = r'''
import json
import os
import re
import shutil
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path("/opt/telegramforward.old")
DATA = ROOT / "data"
sys.path.insert(0, str(ROOT))

from core.config import STATE_DIR, ACCOUNTS
from core.groups_store import load_master_groups, save_master_groups, GROUPS_FILE

SUCCESS_RESULTS = frozenset({"sent", "joined_sent", "pre_joined"})
HARD_FAIL = frozenset({"blocked", "invalid", "cant_write"})


def load_json_list(path: Path) -> set[str]:
    if not path.exists():
        return set()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(data, list):
            return {str(x).strip().lstrip("@") for x in data if x}
        if isinstance(data, dict):
            return {str(k).strip().lstrip("@") for k in data if k}
    except Exception:
        pass
    return set()


def normalize(name: str) -> str:
    return re.sub(r"^@+", "", (name or "").strip()).lower()


def main():
    master = load_master_groups()
    if not master:
        print("ERROR: empty master list")
        return 1

    master_map = {normalize(g): g for g in master}
    master_norm = set(master_map.keys())

    blocked_any: set[str] = set()
    invalid_any: set[str] = set()
    success_any: set[str] = set()
    error_only: set[str] = set()

    for slot in ACCOUNTS:
        base = Path(STATE_DIR) / slot
        if not base.exists():
            continue
        blocked_any |= {normalize(x) for x in load_json_list(base / "blocked_groups.json")}
        invalid_any |= {normalize(x) for x in load_json_list(base / "invalid_groups.json")}

        gi_path = base / "group_intelligence.json"
        if not gi_path.exists():
            continue
        try:
            gi = json.loads(gi_path.read_text(encoding="utf-8"))
        except Exception:
            continue
        for g, info in (gi.get("groups") or {}).items():
            gn = normalize(g)
            if not isinstance(info, dict):
                continue
            lr = str(info.get("last_result") or info.get("status") or "").lower()
            if lr in SUCCESS_RESULTS:
                success_any.add(gn)
            elif lr in HARD_FAIL:
                blocked_any.add(gn)
            elif lr == "invalid":
                invalid_any.add(gn)

    # Global invalid registry
    reg = DATA / "invalid_username_registry.json"
    if reg.exists():
        try:
            reg_data = json.loads(reg.read_text(encoding="utf-8"))
            if isinstance(reg_data, dict):
                invalid_any |= {normalize(k) for k in reg_data}
            elif isinstance(reg_data, list):
                invalid_any |= {normalize(x) for x in reg_data}
        except Exception:
            pass

    # Quality keep file from prior manual review
    quality_keep = set()
    qpath = DATA / "groups_list_quality_keep.txt"
    if qpath.exists():
        for line in qpath.read_text(encoding="utf-8", errors="replace").splitlines():
            line = line.strip()
            m = re.match(r"^\d+\.\s+@?([a-zA-Z0-9_]+)", line)
            if m:
                quality_keep.add(normalize(m.group(1)))
            elif re.match(r"^@?[a-zA-Z0-9_]{3,}$", line):
                quality_keep.add(normalize(line.lstrip("@")))

    remove = (blocked_any | invalid_any) & master_norm
    # Never remove proven successes
    remove -= success_any
    # Quality keep overrides removal if not hard-blocked everywhere
    if quality_keep:
        remove -= quality_keep

    keep_norm = master_norm - remove

    # Score keep list: successes first, then untested (never in intel), then rest
    def score(gn: str) -> tuple:
        if gn in success_any:
            return (0, gn)
        if gn not in blocked_any and gn not in invalid_any:
            return (1, gn)
        return (2, gn)

    keep_sorted = sorted(keep_norm, key=score)
    target_max = 150
    target_min = 100
    if len(keep_sorted) > target_max:
        # Drop lowest priority (non-success, was in error states) until 150
        keep_sorted = keep_sorted[:target_max]

    keep = [master_map[gn] for gn in keep_sorted if gn in master_map]

    print(f"Master total: {len(master)}")
    print(f"Blocked/invalid union (in master): {len(remove)}")
    print(f"Success on any account: {len(success_any & master_norm)}")
    print(f"Quality keep file entries: {len(quality_keep)}")
    print(f"Final keep list: {len(keep)}")

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup = DATA / f"groups_list_backup_{len(master)}_{ts}.json"
    if GROUPS_FILE and os.path.exists(GROUPS_FILE):
        shutil.copy2(GROUPS_FILE, backup)
        print(f"Backup: {backup}")

    save_master_groups(keep)

    upload_txt = DATA / "groups_list_clean_upload.txt"
    with open(upload_txt, "w", encoding="utf-8") as f:
        f.write(f"Telegram Groups List — cleaned ({len(keep)} total)\n")
        f.write("=" * 40 + "\n\n")
        for i, g in enumerate(keep, 1):
            f.write(f"{i}. {g}\n")

    remove_path = DATA / "groups_list_clean_removed.txt"
    removed = sorted(master_map[gn] for gn in remove if gn in master_map)
    with open(remove_path, "w", encoding="utf-8") as f:
        f.write(f"Removed ({len(removed)} groups)\n")
        f.write("=" * 40 + "\n\n")
        for i, g in enumerate(removed, 1):
            f.write(f"{i}. {g}\n")

    print(f"Applied: {GROUPS_FILE}")
    print(f"Upload copy: {upload_txt}")
    print(f"Removed list: {remove_path}")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
'''

RESTART_SCRIPT = '''
import json, time, urllib.request, sys
from pathlib import Path
sys.path.insert(0, "/opt/telegramforward.old")
from core.dashboard_auth_vps import get_credentials, create_session_token, SESSION_COOKIE
from core.config import ACCOUNTS
from core.groups_store import load_master_groups
from core.group_assignment import partition_summary

master = load_master_groups()
print(f"Master now: {len(master)} groups")
for slot in ["account3", "account5", "account8", "account10"]:
    p = partition_summary(slot, master)
    print(f"  {slot}: assigned {p['assigned_count']} ({p['share_pct']}%)")

user, pw = get_credentials()
token = create_session_token(user, role="admin")

def post(path):
    req = urllib.request.Request("http://127.0.0.1:8000" + path, method="POST", data=b"")
    req.add_header("Cookie", f"{SESSION_COOKIE}={token}")
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read().decode()

# Graceful stop campaign workers then restart
campaign_slots = ["account3", "account5", "account7", "account8", "account10"]
for slot in campaign_slots:
    try:
        post(f"/account/{slot}/stop?feature=campaign")
    except Exception as e:
        print(f"stop {slot}: {e}")
time.sleep(3)
for slot in campaign_slots:
    try:
        print(f"start {slot}:", post(f"/account/{slot}/start?feature=campaign"))
    except Exception as e:
        print(f"start {slot}: {e}")

print("sleep 120s for first cycles...")
time.sleep(120)
for slot in campaign_slots:
    p = Path(f"/opt/telegramforward.old/data/accounts/{slot}/cycle_metrics_last.json")
    if p.exists():
        cm = json.loads(p.read_text())
        age = int(time.time() - float(cm.get("ended_at") or 0))
        print(f"{slot}: success={cm.get('success')} skipped={cm.get('skipped')} failed={cm.get('failed')} "
              f"groups={cm.get('groups_processed')} age={age}s")
'''


def run_remote(script: str, timeout: int = 180) -> str:
    sock = socket.create_connection(("187.127.169.159", 22), timeout=30)
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(hostname="187.127.169.159", username="root", password=PASSWORD, sock=sock)
    sftp = c.open_sftp()
    remote_path = "/tmp/group_cleanup_run.py"
    with sftp.open(remote_path, "w") as f:
        f.write(script)
    sftp.close()
    _, stdout, stderr = c.exec_command(
        f"/opt/telegramforward.old/venv/bin/python {remote_path} 2>&1",
        timeout=timeout,
    )
    out = stdout.read().decode("utf-8", errors="replace")
    err = stderr.read().decode("utf-8", errors="replace")
    c.close()
    return out + (f"\nSTDERR: {err}" if err.strip() else "")


if __name__ == "__main__":
    print("=== BUILD & APPLY CLEAN LIST ===")
    print(run_remote(CLEANUP_SCRIPT, timeout=120))
    print("\n=== RESTART CAMPAIGN WORKERS ===")
    print(run_remote(RESTART_SCRIPT, timeout=200))
