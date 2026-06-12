#!/usr/bin/env python3
import socket, paramiko, sys
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
PASSWORD = "REMOVED_VPS_PASSWORD"
sock = socket.create_connection(("187.127.169.159", 22), timeout=30)
c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(hostname="187.127.169.159", username="root", password=PASSWORD, sock=sock)
cmds = [
    "tail -80 /opt/telegramforward.old/docs/SCALABILITY.md",
    "grep -n 'stub\\|Phase\\|not active\\|planned\\|WIP\\|TODO' /opt/telegramforward.old/messaging/queue_backend.py /opt/telegramforward.old/docs/*.md 2>/dev/null | head -40",
    "grep -rn 'stub\\|NotImplemented\\|pass  # TODO\\|# TODO' /opt/telegramforward.old/messaging /opt/telegramforward.old/core /opt/telegramforward.old/services /opt/telegramforward.old/workers 2>/dev/null | grep -v __pycache__ | head -30",
    "head -60 /opt/telegramforward.old/docs/KARTHIK_PLAYBOOKS.md",
    "head -50 /opt/telegramforward.old/docs/FORWARD_MESSAGE_BATCH.md",
]
for cmd in cmds:
    print(f"\n=== {cmd[:65]} ===")
    _, stdout, _ = c.exec_command(cmd, timeout=30)
    print(stdout.read().decode(errors="replace")[:3500] or "(empty)")
c.close()
