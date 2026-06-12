#!/usr/bin/env python3
import json, socket, paramiko, sys, time
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
PASSWORD = "8897870998s@SS"
sock = socket.create_connection(("187.127.169.159", 22), timeout=30)
c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(hostname="187.127.169.159", username="root", password=PASSWORD, sock=sock)

script = r'''
import json, urllib.request, urllib.parse

def post(path, data=None):
    req = urllib.request.Request("http://127.0.0.1:8000" + path, method="POST")
    req.add_header("Content-Type", "application/json")
    if data is not None:
        req.data = json.dumps(data).encode()
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read())

def get(path):
    with urllib.request.urlopen("http://127.0.0.1:8000" + path, timeout=30) as r:
        return json.loads(r.read())

post("/auth/login", {"username": "admin", "password": "734720077743"})
st = get("/state")
campaign = []
for slot, acct in sorted(st.get("accounts", {}).items()):
    cr = acct.get("campaign_running")
    fr = acct.get("forwarding_running")
    if cr or slot in ("account3","account5","account7","account8","account10"):
        campaign.append({
            "slot": slot,
            "running": acct.get("running"),
            "campaign_running": cr,
            "forwarding_running": fr,
            "status": acct.get("status"),
            "notification": acct.get("notification"),
            "cycle": acct.get("campaign_cycle"),
            "success": acct.get("campaign_success"),
            "failed": acct.get("campaign_failed"),
            "my_groups": acct.get("campaign_my_groups"),
            "current_group": acct.get("campaign_current_group"),
            "health_score": acct.get("health_score"),
        })
print("CAMPAIGN STATE:")
print(json.dumps(campaign, indent=2))

# recent logs from state
for slot in ["account3","account5","account7","account8","account10"]:
    logs = st.get("accounts", {}).get(slot, {}).get("logs", [])[-15:]
    print(f"\n=== {slot} last logs ===")
    for L in logs:
        msg = L.get("message") or L.get("text") or str(L)
        print(msg[:200])
'''

_, stdout, stderr = c.exec_command(f"python3 - <<'PY'\n{script}\nPY", timeout=60)
print(stdout.read().decode(errors="replace"))
err = stderr.read().decode(errors="replace")
if err.strip():
    print("ERR:", err)

# grep Unexpected error in app log files
_, stdout, _ = c.exec_command("grep -r 'Unexpected error' /opt/telegramforward.old/data/ 2>/dev/null | tail -20", timeout=60)
print("\n=== Unexpected error in data ===")
print(stdout.read().decode(errors="replace") or "(none)")

c.close()
