#!/usr/bin/env python3
import socket, paramiko, sys
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
PASSWORD = "8897870998s@SS"
sock = socket.create_connection(("187.127.169.159", 22), timeout=30)
c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(hostname="187.127.169.159", username="root", password=PASSWORD, sock=sock)
_, stdout, _ = c.exec_command("grep -n 'st\\.' /opt/telegramforward.old/workers/account_worker.py | grep -E 'health_score|heavy_rate|flood_streak|delay_multiplier|my_groups|status' | head -40", timeout=30)
print(stdout.read().decode(errors="replace"))
_, stdout, _ = c.exec_command("sed -n '1,50p' /opt/telegramforward.old/workers/account_state.py", timeout=30)
print("\n=== account_state top ===")
print(stdout.read().decode(errors="replace"))
_, stdout, _ = c.exec_command("cat /opt/telegramforward.old/workers/feature_runtime.py", timeout=30)
print("\n=== feature_runtime ===")
print(stdout.read().decode(errors="replace"))
c.close()
