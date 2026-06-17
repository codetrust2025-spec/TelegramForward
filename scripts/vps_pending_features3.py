#!/usr/bin/env python3
import socket, paramiko, sys
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
PASSWORD = "REMOVED_VPS_PASSWORD"
sock = socket.create_connection(("187.127.169.159", 22), timeout=30)
c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(hostname="187.127.169.159", username="root", password=PASSWORD, sock=sock)
cmds = [
    "grep -n Gupshup /opt/telegramforward.old/docs/WHATSAPP_INTEGRATION.md",
    "tail -25 /opt/telegramforward.old/docs/WHATSAPP_INTEGRATION.md",
    "test -f /opt/telegramforward.old/workers/runner.py && echo runner:exists || echo runner:missing",
    "grep -rn 'coming soon' /opt/telegramforward.old/dashboard/src 2>/dev/null",
    "grep -rn 'NotImplemented\\|stub' /opt/telegramforward.old/messaging /opt/telegramforward.old/services/whatsapp_gupshup.py 2>/dev/null",
    "head -100 /opt/telegramforward.old/docs/production-update.html 2>/dev/null || ls /opt/telegramforward.old/docs/",
]
for cmd in cmds:
    print(f"\n=== {cmd} ===")
    _, stdout, _ = c.exec_command(cmd, timeout=30)
    print(stdout.read().decode(errors="replace")[:3000] or "(empty)")
c.close()
