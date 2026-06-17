#!/usr/bin/env python3
import os, paramiko
PWD = os.environ.get("VPS_PASSWORD", "")
ROOT = "/opt/telegramforward.old"
SLOTS = ["account1", "account2", "account4", "account8"]
c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect("187.127.169.159", "root", PWD, timeout=30)
parts = []
for s in SLOTS:
    parts.append(f"echo '=== {s} send_history ==='; cat {ROOT}/data/state/{s}/send_history.json 2>/dev/null | head -c 4000")
    parts.append(f"echo '=== {s} group_send_history ==='; cat {ROOT}/data/state/{s}/group_send_history.json 2>/dev/null | head -c 2000")
parts.append(f"echo '=== stats_reset ==='; cat {ROOT}/data/stats_reset.json 2>/dev/null")
parts.append(f"echo '=== running_slots ==='; cat {ROOT}/data/running_slots.json 2>/dev/null")
parts.append("grep -i 'Auto-shutdown' /root/.pm2/logs/telegram-backend-out.log 2>/dev/null | tail -20")
_, o, _ = c.exec_command(" ; ".join(parts), timeout=120)
print(o.read().decode("utf-8", errors="replace"))
c.close()
