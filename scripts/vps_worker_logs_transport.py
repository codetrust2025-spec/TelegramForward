#!/usr/bin/env python3
"""SSH via raw socket (works when getaddrinfo fails on Windows)."""
from __future__ import annotations

import os
import socket
import sys

import paramiko

HOST = "187.127.169.159"
USER = "root"
PASSWORD = os.environ.get("VPS_PASSWORD", "")


def run_remote(script: str, timeout: int = 300) -> tuple[str, str, int]:
    sock = socket.create_connection((HOST, 22), timeout=30)
    transport = paramiko.Transport(sock)
    transport.connect(username=USER, password=PASSWORD)
    chan = transport.open_session()
    chan.settimeout(timeout)
    cmd = f"cd /opt/telegramforward.old && ./venv/bin/python3 - <<'PY'\n{script}\nPY"
    chan.exec_command(cmd)
    out = b""
    err = b""
    while True:
        if chan.recv_ready():
            out += chan.recv(65535)
        if chan.recv_stderr_ready():
            err += chan.recv_stderr(65535)
        if chan.exit_status_ready():
            while chan.recv_ready():
                out += chan.recv(65535)
            while chan.recv_stderr_ready():
                err += chan.recv_stderr(65535)
            break
    code = chan.recv_exit_status()
    transport.close()
    return out.decode("utf-8", errors="replace"), err.decode("utf-8", errors="replace"), code


REMOTE = r'''
import json, re
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path("/opt/telegramforward.old")
DATA = ROOT / "data"
SLOTS = ["account1", "account2", "account4", "account8"]
PM2 = Path("/root/.pm2/logs/telegram-backend-out.log")

print("=== get_last_post_timestamp source ===")
import inspect, sys, os
sys.path.insert(0, str(ROOT)); os.chdir(ROOT)
from core import send_stats as ss
print(inspect.getsource(ss.get_last_post_timestamp))

print("\n=== .running_workers / stats_reset ===")
for fn in [".running_workers.json", "stats_reset.json"]:
    p = DATA / fn
    print(fn, p.read_text() if p.exists() else "missing")

# PM2 full grep with categorization
text = PM2.read_text(errors="replace") if PM2.exists() else ""
print(f"\nPM2 log size: {len(text)} chars, {text.count(chr(10))} lines")

# Patterns for structured worker logs in PM2
for slot in SLOTS:
    print("\n" + "=" * 60)
    print(f"PM2 ANALYSIS: {slot}")
    print("=" * 60)
    lines = [ln for ln in text.splitlines() if slot in ln]
    print(f"Total lines mentioning {slot}: {len(lines)}")

    cats = Counter()
    samples = defaultdict(list)
    for ln in lines:
        ll = ln.lower()
        cat = "other"
        if "auto-shutdown" in ll or "shutdown list" in ll:
            cat = "shutdown"
        elif "graceful shutdown" in ll:
            cat = "process_restart"
        elif "skip" in ll or "still_latest" in ll or "already_last" in ll or "message_recent" in ll:
            cat = "skip"
        elif " sent " in ll or "message sent" in ll or "joined and message sent" in ll or "action=sent" in ll:
            cat = "sent"
        elif "fail" in ll or "error" in ll or "blocked" in ll or "cant_write" in ll or "flood" in ll:
            cat = "fail/error"
        elif "worker start" in ll or "worker started" in ll or "cycle_start" in ll:
            cat = "worker_start"
        elif "worker stop" in ll or "stopping" in ll:
            cat = "worker_stop"
        elif "ai_smart_reply" in ll or "inbox" in ll or "crm" in ll:
            cat = "inbox/crm"
        elif "rate" in ll or "sleeping" in ll or "cooldown" in ll:
            cat = "rate_limit"
        cats[cat] += 1
        if cat not in ("other", "process_restart") and len(samples[cat]) < 5:
            samples[cat].append(ln[:450])

    print("Categories:", dict(cats))
    for cat, samps in samples.items():
        print(f"\n  -- {cat} samples --")
        for s in samps:
            print("   ", s)

# Search for ISO timestamp structured logs (account worker format)
# e.g. "INFO account1 cycle=... SKIP"
for slot in SLOTS:
    pat = re.compile(rf"\b{slot}\b.*(?:SKIP|SENT|FAIL|FLOOD|CYCLE_START|Worker started)", re.I)
    hits = [ln for ln in text.splitlines() if pat.search(ln)]
    print(f"\n=== Structured worker events {slot}: {len(hits)} ===")
    for ln in hits[-25:]:
        print(ln[:450])

# data/logs directory
logs_dir = DATA / "logs"
if logs_dir.exists():
    print(f"\n=== data/logs files: {list(logs_dir.iterdir())[:20]} ===")
else:
    print("\n=== data/logs: MISSING ===")

# state dir per slot
for slot in SLOTS:
    sd = DATA / "state" / slot
    if sd.exists():
        print(f"\nstate/{slot}/:", [p.name for p in sd.iterdir()])
        sh = sd / "send_history.json"
        if sh.exists():
            print(" send_history:", sh.read_text()[:2000])

print("\nDONE")
'''

def main():
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if not PASSWORD:
        raise SystemExit("Set VPS_PASSWORD")
    out, err, code = run_remote(REMOTE)
    path = os.path.join(os.environ.get("TEMP", "."), "vps_worker_logs_full.txt")
    open(path, "w", encoding="utf-8").write(out + "\n" + err)
    print(out)
    if err.strip():
        print("STDERR:", err[:3000])
    print(f"\nSaved: {path}")
    if code != 0:
        raise SystemExit(code)

if __name__ == "__main__":
    main()
