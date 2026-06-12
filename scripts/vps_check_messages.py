#!/usr/bin/env python3
import socket, paramiko, sys, json
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
PASSWORD = "8897870998s@SS"
sock = socket.create_connection(("187.127.169.159", 22), timeout=30)
c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(hostname="187.127.169.159", username="root", password=PASSWORD, sock=sock)

script = r'''
import json
from pathlib import Path

ROOT = Path("/opt/telegramforward.old")

# fleet defaults file
fd = ROOT / "data" / "fleet_defaults.json"
if fd.exists():
    d = json.loads(fd.read_text(encoding="utf-8"))
    cm = (d.get("campaign_message") or "")[:120]
    print("FLEET DEFAULT (first 120 chars):", repr(cm))
else:
    print("No fleet_defaults.json")

global_msg = ROOT / "data" / "custom_message.txt"
if global_msg.exists():
    print("GLOBAL custom_message.txt (120):", repr(global_msg.read_text(encoding="utf-8")[:120]))

campaign = ["account3","account5","account7","account8","account10"]
needle = "From Calls to Offer"
needle2 = "Calls to Offer"

print("\nPER-ACCOUNT message.txt vs running:")
from core.posting_mode import load_posting_mode
from services.account_manager import manager

state = manager.build_ui_state()
st = state.get("account_states") or {}
modes = state.get("posting_modes") or {}

for slot in campaign:
    path = ROOT / "data" / "accounts" / slot / "message.txt"
    text = path.read_text(encoding="utf-8") if path.exists() else ""
    pm = load_posting_mode(slot)
    a = st.get(slot) or {}
    has_new = needle in text or "Your competition" in text
    print(f"  {slot}: campaign={pm.campaign_enabled} running={a.get('campaign_running')} status={a.get('status')}")
    print(f"    file exists={path.exists()} has_new_text={has_new}")
    print(f"    preview: {text[:90].replace(chr(10),' | ')}")

print("\nFORWARDING (for comparison - use t.me link not message):")
for slot in ["account1","account2","account4","account6","account9"]:
    a = st.get(slot) or {}
    pm = load_posting_mode(slot)
    fwd = (pm.forwarding or {}) if hasattr(pm, 'forwarding') else {}
    print(f"  {slot}: fwd={pm.forwarding_enabled} running={a.get('forwarding_running')} source={getattr(pm, 'forwarding', None)}")
'''
_, stdout, stderr = c.exec_command(
    f"cd /opt/telegramforward.old && set -a && . ./.env && set +a && PYTHONPATH=. ./venv/bin/python - <<'PY'\n{script}\nPY",
    timeout=90,
)
print(stdout.read().decode("utf-8", errors="replace"))
err = stderr.read().decode("utf-8", errors="replace")
if err.strip(): print("ERR:", err[-3000:])
c.close()
