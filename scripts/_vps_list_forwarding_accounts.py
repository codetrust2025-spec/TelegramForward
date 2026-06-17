"""List which account slots are in forwarding mode on production."""
import json
import os
import paramiko

PWD = os.environ.get("VPS_PASSWORD", "")
DATA = "/opt/telegramforward.old/data/accounts"

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect("187.127.169.159", username="root", password=PWD, timeout=30)

_, o, _ = c.exec_command(
    f"curl -s http://127.0.0.1:8000/state",
    timeout=30,
)
raw = o.read().decode("utf-8", errors="replace")
try:
    state = json.loads(raw)
except json.JSONDecodeError:
    print("state parse failed:", raw[:500])
    state = {}

info = state.get("account_info") or {}
pm = state.get("posting_modes") or {}
states = state.get("account_states") or {}

print("Forwarding-mode accounts:\n")
for slot in sorted(pm.keys()):
    mode = (pm.get(slot) or {}).get("mode") or "campaign"
    if mode != "forwarding":
        continue
    label = (info.get(slot) or {}).get("name") or slot
    running = bool((states.get(slot) or {}).get("running"))
    fwd = (pm.get(slot) or {}).get("forwarding") or {}
    src = fwd.get("source_type") or "template"
    print(f"  {slot} — {label}")
    print(f"    running: {running}")
    print(f"    source: {src}")
    if fwd.get("source_label"):
        print(f"    t.me source: {fwd.get('source_label')}")

print("\nCampaign-mode count:", sum(1 for s in pm if (pm[s] or {}).get("mode") != "forwarding"))
print("Forwarding-mode count:", sum(1 for s in pm if (pm[s] or {}).get("mode") == "forwarding"))

c.close()
