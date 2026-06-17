#!/usr/bin/env python3
import os, socket, sys, json
import paramiko

HOST, USER = "187.127.169.159", "root"
PWD = os.environ.get("VPS_PASSWORD", "")

SCRIPT = r'''
import json, urllib.request
raw = urllib.request.urlopen("http://127.0.0.1:8000/state", timeout=30).read()
st = json.loads(raw)
active = [f"account{i}" for i in range(1, 11)]
print("fleet_running", st.get("running"))
print("active_account", st.get("active_account"))
ds = st.get("daily_stats") or {}
g = ds.get("global") or {}
print("daily forward_posts", g.get("forward_posts"), "campaign", g.get("campaign_posts"), "window", ds.get("window"))
print("\nAccount forwarding state:")
for slot in active:
    ac = (st.get("account_states") or {}).get(slot) or {}
    info = (st.get("account_info") or {}).get(slot)
    fwd = ac.get("forwarding") or {}
    camp = ac.get("campaign") or {}
    pa = (ds.get("per_account") or {}).get(slot) or {}
    mode = (st.get("posting_modes") or {}).get(slot) or {}
    logged = bool(info and info.get("phone"))
    print(
        f"{slot}: logged={logged} fwd_run={fwd.get('running')} camp_run={camp.get('running')} "
        f"tick_ok={fwd.get('tick_ok')} tick_success={fwd.get('success')} "
        f"today_fwd={pa.get('forward_posts')} today_camp={pa.get('campaign_posts')} "
        f"mode={mode.get('mode')} fwd_en={mode.get('forwarding_enabled')}"
    )
'''

def main():
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sock = socket.create_connection((HOST, 22), timeout=30)
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(HOST, username=USER, password=PWD, sock=sock)
    cmd = f"cd /opt/telegramforward.old && source venv/bin/activate && python3 << 'PYEOF'\n{SCRIPT}\nPYEOF"
    _, o, e = c.exec_command(cmd, timeout=90)
    print(o.read().decode())
    err = e.read().decode().strip()
    if err:
        print("ERR:", err)
    c.close()

if __name__ == "__main__":
    main()
