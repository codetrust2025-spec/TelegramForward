#!/usr/bin/env python3
import socket, paramiko, sys
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
PASSWORD = "8897870998s@SS"
sock = socket.create_connection(("187.127.169.159", 22), timeout=30)
c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(hostname="187.127.169.159", username="root", password=PASSWORD, sock=sock)
for start,end,label in [(1910,2010,"send_loop"), (2990,3080,"result_handler"), (250,350,"dispatch_inline")]:
    _, stdout, _ = c.exec_command(f"sed -n '{start},{end}p' /opt/telegramforward.old/workers/account_worker.py 2>/dev/null; sed -n '{start},{end}p' /opt/telegramforward.old/messaging/message_router.py 2>/dev/null", timeout=30)
    out = stdout.read().decode(errors="replace")
    if out.strip():
        print(f"\n=== {label} {start}-{end} ===")
        print(out[:6000])
c.close()
