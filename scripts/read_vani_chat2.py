#!/usr/bin/env python3
import os, socket, paramiko, json, sys
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
PASSWORD = os.environ.get("VPS_PASSWORD", "")

sock = socket.create_connection(("187.127.169.159", 22), timeout=30)
c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(hostname="187.127.169.159", username="root", password=PASSWORD, sock=sock)
_, stdout, _ = c.exec_command(
    "grep -l 'scratch\\|I need job\\|Vani Sree' /opt/telegramforward.old/data/accounts/account*/dm_inbox.json 2>/dev/null",
    timeout=60,
)
files = stdout.read().decode().strip().splitlines()
c.close()

needles = ["i need job", "scratch", "experience?", "tech stack"]

sock = socket.create_connection(("187.127.169.159", 22), timeout=30)
c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(hostname="187.127.169.159", username="root", password=PASSWORD, sock=sock)
sftp = c.open_sftp()

for fp in files or []:
    with sftp.open(fp, "r") as f:
        d = json.loads(f.read().decode("utf-8", errors="replace"))
    slot = fp.split("/account")[1].split("/")[0]
    convs = d.get("conversations") or {}
    items = convs.items() if isinstance(convs, dict) else [(x.get("user_id"), x) for x in convs]
    for uid, conv in items:
        if not isinstance(conv, dict):
            continue
        blob = json.dumps(conv).lower()
        if not any(n in blob for n in needles):
            continue
        print(f"\n=== account{slot} | {conv.get('name')} | {uid} ===")
        for m in conv.get("messages") or []:
            dr = m.get("direction", "?")
            text = m.get("text") or m.get("message") or "[media]"
            by = m.get("sent_by") or m.get("sender_name") or ""
            ai = " [AI]" if m.get("is_ai") else ""
            who = "LEAD" if dr == "in" else f"REPLY ({by})" if by else "REPLY"
            print(f"  {who}{ai}: {text[:300]}")

sftp.close()
c.close()
