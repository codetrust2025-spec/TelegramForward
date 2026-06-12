#!/usr/bin/env python3
import socket, paramiko, sys
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
PASSWORD = "8897870998s@SS"
sock = socket.create_connection(("187.127.169.159", 22), timeout=30)
c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(hostname="187.127.169.159", username="root", password=PASSWORD, sock=sock)
cmds = [
    "ls /opt/telegramforward.old/*.md /opt/telegramforward.old/docs/*.md 2>/dev/null",
    "grep -rni 'TODO\\|FIXME\\|ROADMAP\\|pending\\|coming soon\\|not yet\\|WIP' /opt/telegramforward.old --include='*.md' --include='*.py' 2>/dev/null | grep -v __pycache__ | grep -v backup | head -60",
    "cat /opt/telegramforward.old/README.md 2>/dev/null | head -80",
    "cat /opt/telegramforward.old/ROADMAP.md 2>/dev/null | head -100",
    "cat /opt/telegramforward.old/docs/ROADMAP.md 2>/dev/null | head -100",
]
for cmd in cmds:
    print(f"\n=== {cmd[:70]} ===")
    _, stdout, _ = c.exec_command(cmd, timeout=45)
    print(stdout.read().decode(errors="replace")[:4000] or "(empty)")
c.close()
