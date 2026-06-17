#!/usr/bin/env python3
import os, socket, paramiko, json, sys
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
PASSWORD = os.environ.get("VPS_PASSWORD", "")

def run(cmd):
    sock = socket.create_connection(("187.127.169.159", 22), timeout=30)
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(hostname="187.127.169.159", username="root", password=PASSWORD, sock=sock)
    _, stdout, stderr = c.exec_command(cmd, timeout=120)
    out = stdout.read().decode("utf-8", "replace")
    err = stderr.read().decode("utf-8", "replace")
    c.close()
    return out, err

# Try dm_inbox files for account9 and search for Madhu / R.B.
for slot in ["account9", "account1", "account2"]:
    out, err = run(f"test -f /opt/telegramforward.old/data/accounts/{slot}/dm_inbox.json && head -c 8000 /opt/telegramforward.old/data/accounts/{slot}/dm_inbox.json || echo MISSING")
    print(f"\n=== {slot} dm_inbox ===")
    if out.startswith("{") or out.startswith("["):
        try:
            d = json.loads(out[:8000] + ("..." if len(out)>8000 else ""))
        except json.JSONDecodeError:
            # partial - grep instead
            out2, _ = run(f"grep -i 'madhu\\|r.b\\|karthik' /opt/telegramforward.old/data/accounts/{slot}/dm_inbox.json | head -5")
            print(out2 or "parse fail")
            continue
        convs = d if isinstance(d, list) else d.get("conversations", [])
        for c in convs[:20]:
            name = c.get("name") or c.get("username") or ""
            if "madhu" in name.lower() or "r.b" in name.lower() or "r. b" in name.lower():
                print("MATCH:", json.dumps(c, indent=2)[:2000])
    else:
        print(out[:500], err[:200])
