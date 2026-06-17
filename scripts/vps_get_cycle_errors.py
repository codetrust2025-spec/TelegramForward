#!/usr/bin/env python3
import socket, paramiko, sys
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
PASSWORD = "REMOVED_VPS_PASSWORD"
sock = socket.create_connection(("187.127.169.159", 22), timeout=30)
c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(hostname="187.127.169.159", username="root", password=PASSWORD, sock=sock)

cmds = [
    "grep -E 'Unexpected error|Cycle error|cycle_error|Traceback' /root/.pm2/logs/telegram-backend-error.log 2>/dev/null | tail -80",
    "grep -E 'Unexpected error|cycle_error' /opt/telegramforward.old/data/logs/account7.log 2>/dev/null | tail -40",
    "grep -E 'Unexpected error|cycle_error|CYCLE_START|CYCLE_RESUME' /opt/telegramforward.old/data/logs/account7.log 2>/dev/null | tail -30",
    "curl -s -u admin:734720077743 http://127.0.0.1:8000/api/accounts/account7/status 2>/dev/null | python3 -m json.tool 2>/dev/null | head -80",
]
for cmd in cmds:
    print(f"\n=== {cmd[:70]}... ===")
    _, stdout, stderr = c.exec_command(cmd, timeout=60)
    out = stdout.read().decode(errors="replace")
    err = stderr.read().decode(errors="replace")
    print(out or err or "(empty)")

c.close()
