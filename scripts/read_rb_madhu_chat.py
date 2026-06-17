#!/usr/bin/env python3
import os, socket, paramiko, json, re, sys
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
PASSWORD = os.environ.get("VPS_PASSWORD", "")

sock = socket.create_connection(("187.127.169.159", 22), timeout=30)
c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(hostname="187.127.169.159", username="root", password=PASSWORD, sock=sock)
sftp = c.open_sftp()
with sftp.open("/opt/telegramforward.old/data/accounts/account9/dm_inbox.json", "r") as f:
    d = json.loads(f.read().decode("utf-8", errors="replace"))
sftp.close()
c.close()

convs = d.get("conversations") or {}
if isinstance(convs, list):
    items = [(str(c.get("user_id")), c) for c in convs]
else:
    items = list(convs.items())

OUT = []
for uid, c in items:
    if not isinstance(c, dict):
        continue
    name = c.get("name") or c.get("first_name") or ""
    if not re.search(r"madhu|r\.?\s*b", name, re.I):
        continue
    OUT.append(f"=== {name} (user_id={uid}) ===")
    OUT.append(f"Username: {c.get('username')}")
    OUT.append(f"Last: {c.get('last_message')}")
    msgs = c.get("messages") or []
    for m in msgs:
        if not isinstance(m, dict):
            continue
        dr = m.get("direction") or ("out" if m.get("out") else "in")
        text = (m.get("text") or m.get("message") or "").replace("\n", " ")
        ts = m.get("sent_at") or m.get("date") or m.get("time") or ""
        ai = " [AI]" if m.get("is_ai") or m.get("ai") else ""
        who = "Lead" if dr == "in" else "Reply"
        OUT.append(f"  {ts} | {who}: {text}{ai}")

if not OUT:
    # fallback: any conv with only Hi + Karthik greeting today
    for uid, c in items:
        if not isinstance(c, dict):
            continue
        msgs = c.get("messages") or []
        texts = [(m.get("text") or "") for m in msgs if isinstance(m, dict)]
        blob = " ".join(texts)
        if "Hi R.B" in blob or (any(t.strip() == "Hi" for t in texts) and "Karthik" in blob):
            name = c.get("name") or uid
            OUT.append(f"=== {name} (user_id={uid}) ===")
            for m in msgs:
                dr = m.get("direction", "?")
                text = m.get("text", "")
                OUT.append(f"  {dr}: {text}")

text = "\n".join(OUT) if OUT else "No matching conversation found in account9 dm_inbox"
path = os.path.join(os.environ.get("TEMP", "."), "rb_madhu.txt")
open(path, "w", encoding="utf-8").write(text)
print(text)
