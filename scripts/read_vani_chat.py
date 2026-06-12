#!/usr/bin/env python3
import os, socket, paramiko, json, re, sys
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
PASSWORD = os.environ.get("VPS_PASSWORD", "")

def fetch_inbox(slot):
    sock = socket.create_connection(("187.127.169.159", 22), timeout=30)
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(hostname="187.127.169.159", username="root", password=PASSWORD, sock=sock)
    sftp = c.open_sftp()
    path = f"/opt/telegramforward.old/data/accounts/{slot}/dm_inbox.json"
    try:
        with sftp.open(path, "r") as f:
            d = json.loads(f.read().decode("utf-8", errors="replace"))
    except FileNotFoundError:
        d = {}
    sftp.close()
    c.close()
    return d

def read_conv(convs, pattern):
    if isinstance(convs, dict):
        items = convs.items()
    else:
        items = [(c.get("user_id"), c) for c in convs]
    for uid, c in items:
        if not isinstance(c, dict):
            continue
        name = (c.get("name") or "") + " " + (c.get("username") or "")
        if re.search(pattern, name, re.I):
            return uid, c
        for m in (c.get("messages") or []):
            t = m.get("text") or ""
            if "everything should be done by scratch" in t.lower():
                return uid, c
    return None, None

lines = []
for slot in ["account1", "account2", "account9", "account3"]:
    d = fetch_inbox(slot)
    convs = d.get("conversations") or {}
    uid, c = read_conv(convs, r"vani|unknown")
    if not c:
        uid, c = read_conv(convs, r"scratch")
    if c:
        lines.append(f"=== {slot} | {c.get('name')} | user_id={uid} ===")
        lines.append(f"Username: {c.get('username') or '(none)'}")
        lines.append(f"Last: {c.get('last_message')}")
        for m in (c.get("messages") or []):
            dr = m.get("direction") or "?"
            text = (m.get("text") or "").replace("\n", " ")
            ts = m.get("sent_at") or m.get("time") or ""
            by = m.get("sent_by") or m.get("sender_name") or ""
            ai = " [AI]" if m.get("is_ai") or m.get("ai") else ""
            tag = f" ({by})" if by else ""
            who = "LEAD" if dr == "in" else "REPLY"
            lines.append(f"  {ts} | {who}{tag}{ai}: {text}")
        lines.append("")

text = "\n".join(lines) if lines else "Conversation not found in dm_inbox files"
print(text)
