#!/usr/bin/env python3
import socket, paramiko, sys
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
PASSWORD = "8897870998s@SS"
sock = socket.create_connection(("187.127.169.159", 22), timeout=30)
c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(hostname="187.127.169.159", username="root", password=PASSWORD, sock=sock)
for fn in ["_sync_health_to_state", "partition_summary", "prepare_cycle_message", "_load_cycle_checkpoint"]:
    _, stdout, _ = c.exec_command(f"grep -n 'def {fn}' /opt/telegramforward.old/**/*.py 2>/dev/null; grep -rn 'def {fn}' /opt/telegramforward.old/ 2>/dev/null | head -5", timeout=30)
    print(f"\n=== {fn} ===")
    print(stdout.read().decode(errors="replace")[:1500])
c.close()
