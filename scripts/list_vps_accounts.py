#!/usr/bin/env python3
import os, socket, paramiko, sys, json
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
PASSWORD = os.environ.get("VPS_PASSWORD", "")
sock = socket.create_connection(("187.127.169.159", 22), timeout=30)
c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(hostname="187.127.169.159", username="root", password=PASSWORD, sock=sock)

cmd = """
for d in /opt/telegramforward.old/data/accounts/account*; do
  slot=$(basename "$d")
  info="$d/account_info.json"
  if [ -f "$info" ]; then
    echo "=== $slot ==="
    cat "$info"
    echo
  fi
done
ls -d /opt/telegramforward.old/data/accounts/account* 2>/dev/null | wc -l
"""
_, stdout, _ = c.exec_command(cmd, timeout=60)
print(stdout.read().decode(errors="replace"))
c.close()
