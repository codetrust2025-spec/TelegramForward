#!/usr/bin/env python3
import os, socket, sys
import paramiko
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
PASSWORD = os.environ.get("VPS_PASSWORD", "")
REMOTE = "/opt/telegramforward.old"
cmds = [
    f"ls -la {REMOTE}/data/ | head -40",
    f"ls -la {REMOTE}/data/account3/ 2>/dev/null | head -25",
    f"ls -la {REMOTE}/data/account8/ 2>/dev/null | head -25",
    f"find {REMOTE}/data -name message.txt 2>/dev/null | head -20",
    f"find {REMOTE}/data -name cycle_metrics_last.json 2>/dev/null | head -15",
    f"head -c 2000 {REMOTE}/data/accounts_config.json 2>/dev/null",
    f"grep -r output_mode {REMOTE}/data/*.json 2>/dev/null | head -10",
    f"python3 -c \"import json; d=json.load(open('{REMOTE}/data/group_intelligence.json')); print(json.dumps({{k:d.get('accounts',{{}}).get(k) for k in ['account3','account8']}}, indent=2))\" 2>&1",
]
sock = socket.create_connection(("187.127.169.159", 22), timeout=30)
c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(hostname="187.127.169.159", username="root", password=PASSWORD, sock=sock)
for cmd in cmds:
    print(f"\n=== {cmd[:70]} ===")
    _, stdout, _ = c.exec_command(cmd, timeout=30)
    print(stdout.read().decode("utf-8", errors="replace")[:2500])
c.close()
