#!/usr/bin/env python3
import os, socket, paramiko, sys
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HOST, USER = "187.127.169.159", "root"
PWD = os.environ.get("VPS_PASSWORD", "")
BUNDLE = "/opt/telegramforward.old/static/assets/app-D89Ign3q.js"
OUT = r"C:\Users\codet\OneDrive\Desktop\Automation\scripts\app_bundle_accounts_snippet.js"

sock = socket.create_connection((HOST, 22), timeout=30)
c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(hostname=HOST, username=USER, password=PWD, sock=sock)
sftp = c.open_sftp()
with sftp.open(BUNDLE, "r") as f:
    b = f.read().decode("utf-8", errors="replace")
sftp.close()
c.close()

# Extract chunks around key areas
chunks = [
    (201500, 8000, "accounts_section"),
    (569000, 6000, "login_filter"),
    (585000, 4000, "shutdown_helper"),
]
parts = []
for start, size, label in chunks:
    parts.append(f"\n\n/* ===== {label} @ {start} ===== */\n")
    parts.append(b[start:start+size])

text = "".join(parts)
open(OUT, "w", encoding="utf-8").write(text)
print(f"Wrote {len(text)} chars to {OUT}")
