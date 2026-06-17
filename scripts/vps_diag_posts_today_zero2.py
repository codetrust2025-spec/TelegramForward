#!/usr/bin/env python3
"""Check worker status + send history + telegram errors."""
import json, os, socket, sys
import paramiko

HOST, USER = "187.127.169.159", "root"
PWD = os.environ.get("VPS_PASSWORD", "")

SCRIPT = r'''
import json, subprocess
from pathlib import Path
from datetime import datetime, timezone, timedelta
try:
    from zoneinfo import ZoneInfo
    IST = ZoneInfo("Asia/Kolkata")
except Exception:
    IST = timezone(timedelta(hours=5, minutes=30))

def fmt(ts):
    if not ts: return "none"
    return datetime.fromtimestamp(float(ts), tz=IST).strftime("%Y-%m-%d %H:%M IST")

root = Path("/opt/telegramforward.old/data/accounts")
active = ["account1","account2","account3","account4","account5","account6","account7","account8","account9","account10"]

print("=== PM2 worker status (active fleet) ===")
r = subprocess.run(["pm2", "jlist"], capture_output=True, text=True, timeout=30)
procs = json.loads(r.stdout)
for p in procs:
    name = p.get("name", "")
    if not name.startswith("account"):
        continue
    if name not in active and int(name.replace("account","") or 99) > 10:
        continue
    st = p.get("pm2_env", {}).get("status", "?")
    print(f"{name}: {st}")

print("\n=== Send history samples (active accounts) ===")
for slot in active:
    info = root / slot / "account_info.json"
    logged = info.exists() and bool(json.loads(info.read_text()).get("phone"))
    for fname in ["send_history_forward.json", "send_history_campaign.json", "send_history.json"]:
        p = root / slot / fname
        if not p.exists():
            continue
        try:
            data = json.loads(p.read_text())
            ts = data.get("timestamps") if isinstance(data, dict) else data
            if not isinstance(ts, list):
                ts = []
            ts = [float(x) for x in ts if x]
            recent = sorted(ts)[-3:]
            print(f"{slot} {fname}: count={len(ts)} recent={[fmt(t) for t in recent]} logged_in={logged}")
        except Exception as ex:
            print(f"{slot} {fname}: read error {ex}")

print("\n=== Recent errors (account1, account4, account6) ===")
for acc in ["account1", "account4", "account6", "account9"]:
    r = subprocess.run(
        ["bash", "-lc", f"pm2 logs {acc} --lines 40 --nostream 2>&1 | tail -25"],
        capture_output=True, text=True, timeout=20,
    )
    print(f"--- {acc} ---")
    for line in (r.stdout or "").splitlines():
        low = line.lower()
        if any(k in low for k in ["error", "fail", "session", "forward", "tick", "sent", "wrong", "connect"]):
            print(line[:220])

print("\n=== /state tick_ok sample ===")
import urllib.request
try:
    raw = urllib.request.urlopen("http://127.0.0.1:8000/state", timeout=15).read()
    st = json.loads(raw)
    for slot in active[:6]:
        ac = (st.get("account_states") or {}).get(slot) or {}
        fwd = ac.get("forwarding") or {}
        print(f"{slot}: running={fwd.get('running')} tick_ok={fwd.get('tick_ok')} success={fwd.get('success')} failed={fwd.get('failed')}")
except Exception as ex:
    print("state error", ex)
'''

def main():
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sock = socket.create_connection((HOST, 22), timeout=30)
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(HOST, username=USER, password=PWD, sock=sock)
    cmd = f"cd /opt/telegramforward.old && source venv/bin/activate && python3 << 'PYEOF'\n{SCRIPT}\nPYEOF"
    _, o, e = c.exec_command(cmd, timeout=120)
    print(o.read().decode())
    err = e.read().decode().strip()
    if err:
        print("ERR:", err)
    c.close()

if __name__ == "__main__":
    main()
