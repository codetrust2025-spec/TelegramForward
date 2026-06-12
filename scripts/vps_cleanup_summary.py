#!/usr/bin/env python3
import os, socket, sys
import paramiko
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
PASSWORD = os.environ.get("VPS_PASSWORD", "")
REMOTE = "/opt/telegramforward.old/data"
cmds = [
    f"python3 -c \"import json; d=json.load(open('{REMOTE}/groups_list.json')); print('master count:', len(d)); print('sample:', d[:8])\"",
    f"wc -l {REMOTE}/groups_list_clean_removed.txt {REMOTE}/groups_list_clean_upload.txt",
    f"head -15 {REMOTE}/groups_list_clean_removed.txt",
    f"tail -5 {REMOTE}/groups_list_clean_upload.txt",
]
sock = socket.create_connection(("187.127.169.159", 22), timeout=30)
c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(hostname="187.127.169.159", username="root", password=PASSWORD, sock=sock)
for cmd in cmds:
    print(f"\n=== {cmd[:70]} ===")
    _, stdout, _ = c.exec_command(cmd, timeout=20)
    print(stdout.read().decode("utf-8", errors="replace")[:2000])
c.close()
