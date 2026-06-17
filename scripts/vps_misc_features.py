#!/usr/bin/env python3
import socket, paramiko, sys
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
PASSWORD = "8897870998s@SS"
sock = socket.create_connection(("187.127.169.159", 22), timeout=30)
c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(hostname="187.127.169.159", username="root", password=PASSWORD, sock=sock)
_, stdout, _ = c.exec_command("grep -rn 'WHATSAPP\\|voice\\|account11\\|Prometheus\\|workers.runner' /opt/telegramforward.old/docs/*.md /opt/telegramforward.old/.env.example 2>/dev/null | head -25; ls /opt/telegramforward.old/workers/runner* 2>/dev/null; wc -l /opt/telegramforward.old/services/whatsapp_gupshup.py; head -30 /opt/telegramforward.old/services/whatsapp_gupshup.py", timeout=30)
print(stdout.read().decode())
c.close()
