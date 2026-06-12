#!/usr/bin/env python3
import socket, paramiko, sys
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
PASSWORD = "REMOVED_VPS_PASSWORD"
sock = socket.create_connection(("187.127.169.159", 22), timeout=30)
c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(hostname="187.127.169.159", username="root", password=PASSWORD, sock=sock)
docs = [
    "ARCHITECTURE.md", "docs/SCALABILITY.md", "docs/WHATSAPP_INTEGRATION.md",
    "docs/AI_SMART_REPLY.md", "docs/FORWARD_MESSAGE_BATCH.md", "docs/GROUP_LIST_CLEANUP.md",
]
for d in docs:
    _, stdout, _ = c.exec_command(f"head -80 /opt/telegramforward.old/{d} 2>/dev/null", timeout=30)
    text = stdout.read().decode(errors="replace")
    if text.strip():
        print(f"\n{'='*60}\n{d}\n{'='*60}\n{text[:3500]}")
# TODO/FIXME only
_, stdout, _ = c.exec_command(
    "grep -rn '# TODO\\|# FIXME\\|TODO:\\|FIXME:\\|NotImplemented\\|not implemented yet\\|future:' /opt/telegramforward.old --include='*.py' --include='*.md' 2>/dev/null | grep -v backup | grep -v __pycache__ | head -50",
    timeout=45,
)
print("\n=== TODO/FIXME in code ===")
print(stdout.read().decode(errors="replace") or "(none)")
# package version / changelog
_, stdout, _ = c.exec_command("ls /opt/telegramforward.old/CHANGELOG* /opt/telegramforward.old/docs/*.md 2>/dev/null; grep -l 'planned\\|roadmap\\|future\\|phase' /opt/telegramforward.old/docs/*.md 2>/dev/null", timeout=30)
print("\n=== files ===")
print(stdout.read().decode())
c.close()
