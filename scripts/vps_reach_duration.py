#!/usr/bin/env python3
"""Compare forwarding vs campaign reach with time duration (posts/hour)."""
import os, socket, sys, json
import paramiko

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
PASSWORD = os.environ.get("VPS_PASSWORD", "")

SCRIPT = r"""
import json, sys, time, urllib.request
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, '/opt/telegramforward.old')
from core.dashboard_auth_vps import get_credentials, create_session_token, SESSION_COOKIE
from core.stats_reset import get_reset_timestamp, get_reset_at_iso

def iso(ts):
    if not ts: return None
    return datetime.fromtimestamp(float(ts), tz=timezone.utc).strftime('%Y-%m-%d %H:%M UTC')

def fmt_dur(secs):
    secs = max(0, float(secs or 0))
    h = int(secs // 3600)
    m = int((secs % 3600) // 60)
    if h >= 24:
        d, h = divmod(h, 24)
        return f"{d}d {h}h {m}m"
    return f"{h}h {m}m"

user, pw = get_credentials()
token = create_session_token(user, role='admin')
req = urllib.request.Request('http://127.0.0.1:8000/state')
req.add_header('Cookie', f'{SESSION_COOKIE}={token}')
state = json.loads(urllib.request.urlopen(req, timeout=20).read())
now = time.time()

ds = state.get('daily_stats') or {}
pa = ds.get('per_account') or {}
posting_modes = state.get('posting_modes') or {}
acct_states = state.get('account_states') or {}

reset_ts = get_reset_timestamp()
reset_iso = get_reset_at_iso() or ds.get('reset_at')
window_secs = (now - reset_ts) if reset_ts else 86400
window_label = 'since_reset' if reset_ts else 'rolling_24h'

print('=== Stats window ===')
print(f'window: {window_label}')
print(f'reset_at: {reset_iso}')
print(f'elapsed: {fmt_dur(window_secs)} ({window_secs/3600:.2f} hours)')
print(f'now: {iso(now)}')
print()

# Classify accounts by mode
fwd_slots, camp_slots, both_slots = [], [], []
for slot in sorted(acct_states.keys()):
    pm_raw = posting_modes.get(slot) or acct_states[slot].get('posting_mode') or ''
    if isinstance(pm_raw, dict):
        fwd_on = bool(pm_raw.get('forwarding'))
        camp_on = bool(pm_raw.get('campaign'))
    else:
        pm = str(pm_raw).lower()
        fwd_on = pm in ('forwarding', 'both')
        camp_on = pm in ('campaign', 'both')
    if not fwd_on:
        fwd_on = bool((acct_states[slot].get('forwarding') or {}).get('running'))
    if not camp_on:
        camp_on = bool((acct_states[slot].get('campaign') or {}).get('running'))
    if fwd_on and camp_on:
        both_slots.append(slot)
    elif fwd_on:
        fwd_slots.append(slot)
    elif camp_on:
        camp_slots.append(slot)

print('=== Account modes ===')
print(f'forwarding-only: {", ".join(fwd_slots) or "none"}')
print(f'campaign-only: {", ".join(camp_slots) or "none"}')
print(f'both: {", ".join(both_slots) or "none"}')
print()

fwd_total = camp_total = 0
rows = []
for slot in sorted(pa.keys()):
    row = pa[slot]
    fp = int(row.get('forward_posts') or 0)
    cp = int(row.get('campaign_posts') or 0)
    fwd_total += fp
    camp_total += cp
    if fp or cp:
        a = acct_states.get(slot) or {}
        ws = float(a.get('worker_started_at') or 0)
        run_secs = (now - ws) if ws > 0 else None
        f_rt = a.get('forwarding') or {}
        c_rt = a.get('campaign') or {}
        rows.append({
            'slot': slot,
            'fp': fp, 'cp': cp,
            'run_secs': run_secs,
            'fwd_cycle': int(f_rt.get('cycle') or 0),
            'camp_cycle': int(c_rt.get('cycle') or 0),
            'fwd_next': int(f_rt.get('next_cycle_in') or 0),
            'camp_next': int(c_rt.get('next_cycle_in') or 0),
            'fwd_running': bool(f_rt.get('running')),
            'camp_running': bool(c_rt.get('running')),
        })

print('=== Per-account reach + runtime ===')
print(f'{"slot":<12} {"fwd":>6} {"camp":>6} {"run_time":>12} {"fwd_cyc":>8} {"camp_cyc":>8} {"status":<20}')
for r in rows:
    status = []
    if r['fwd_running']: status.append('fwd:run')
    if r['camp_running']: status.append('camp:run')
    print(f"{r['slot']:<12} {r['fp']:>6} {r['cp']:>6} {fmt_dur(r['run_secs'] or 0):>12} {r['fwd_cycle']:>8} {r['camp_cycle']:>8} {' '.join(status) or 'idle':<20}")

hours = window_secs / 3600.0 if window_secs > 0 else 1.0
fwd_rate = fwd_total / hours
camp_rate = camp_total / hours

print()
print('=== Fleet totals (since reset window) ===')
print(f'Forwarding posts: {fwd_total}')
print(f'Campaign posts:   {camp_total}')
print(f'Forwarding rate:  {fwd_rate:.1f} posts/hour')
print(f'Campaign rate:    {camp_rate:.1f} posts/hour')
print()

# Mode-scoped rates (only accounts dedicated to one mode)
def sum_mode(slots, key):
    return sum(int((pa.get(s) or {}).get(key) or 0) for s in slots)

fwd_only_posts = sum_mode(fwd_slots, 'forward_posts')
camp_only_posts = sum_mode(camp_slots, 'campaign_posts')
both_fwd = sum_mode(both_slots, 'forward_posts')
both_camp = sum_mode(both_slots, 'campaign_posts')

print('=== By dedicated accounts ===')
print(f'Forwarding-only accounts ({len(fwd_slots)}): {fwd_only_posts} posts ({fwd_only_posts/hours:.1f}/hr)')
print(f'Campaign-only accounts ({len(camp_slots)}): {camp_only_posts} posts ({camp_only_posts/hours:.1f}/hr)')
print(f'Both-mode accounts ({len(both_slots)}): fwd={both_fwd} camp={both_camp}')
print()

# Current tick throughput estimate (cycle countdown)
fwd_next = [int((acct_states.get(s, {}).get('forwarding') or {}).get('next_cycle_in') or 0) for s in acct_states if (acct_states[s].get('forwarding') or {}).get('running')]
camp_next = [int((acct_states.get(s, {}).get('campaign') or {}).get('next_cycle_in') or 0) for s in acct_states if (acct_states[s].get('campaign') or {}).get('running')]
print('=== Cycle timing (current) ===')
print(f'Forwarding accounts running: {len(fwd_next)} | next cycle in: {min(fwd_next) if fwd_next else "n/a"}s – {max(fwd_next) if fwd_next else "n/a"}s')
print(f'Campaign accounts running:   {len(camp_next)} | next cycle in: {min(camp_next) if camp_next else "n/a"}s – {max(camp_next) if camp_next else "n/a"}s')

# Winner
print()
if fwd_rate > camp_rate:
    pct = ((fwd_rate / camp_rate) - 1) * 100 if camp_rate else 100
    print(f'WINNER (volume rate): FORWARDING — {fwd_rate:.1f}/hr vs {camp_rate:.1f}/hr ({pct:.0f}% faster)')
else:
    pct = ((camp_rate / fwd_rate) - 1) * 100 if fwd_rate else 100
    print(f'WINNER (volume rate): CAMPAIGN — {camp_rate:.1f}/hr vs {fwd_rate:.1f}/hr ({pct:.0f}% faster)')

if camp_only_posts/hours > fwd_only_posts/hours if fwd_slots else camp_rate > fwd_rate:
    print('WINNER (dedicated accounts rate): see dedicated section above')
"""

sock = socket.create_connection(("187.127.169.159", 22), timeout=30)
c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(hostname="187.127.169.159", username="root", password=PASSWORD, sock=sock)
sftp = c.open_sftp()
with sftp.open("/tmp/reach_duration.py", "w") as f:
    f.write(SCRIPT)
sftp.close()
_, stdout, stderr = c.exec_command(
    "/opt/telegramforward.old/venv/bin/python /tmp/reach_duration.py 2>&1", timeout=60
)
print(stdout.read().decode())
err = stderr.read().decode()
if err.strip():
    print("[stderr]", err)
c.close()
