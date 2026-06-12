#!/usr/bin/env python3
"""Fetch VPS campaign fixes + diagnose account3/account8."""
import json
import os
import socket
import sys
from pathlib import Path

import paramiko

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

PASSWORD = os.environ.get("VPS_PASSWORD", "")
REMOTE = "/opt/telegramforward.old"
LOCAL_TF = Path(r"C:\Users\codet\TelegramForward")
OUT = Path(__file__).resolve().parent / "vps_fetched"

def run(c, cmd, timeout=60):
    _, stdout, stderr = c.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode("utf-8", errors="replace")
    err = stderr.read().decode("utf-8", errors="replace")
    return out, err

def main():
    OUT.mkdir(exist_ok=True)
    sock = socket.create_connection(("187.127.169.159", 22), timeout=30)
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(hostname="187.127.169.159", username="root", password=PASSWORD, sock=sock)

    files = [
        "workers/feature_runtime.py",
        "workers/account_worker.py",
        "workers/account_state.py",
    ]
    sftp = c.open_sftp()
    for rel in files:
        remote = f"{REMOTE}/{rel}"
        local = OUT / rel.replace("/", "_")
        try:
            sftp.get(remote, str(local))
            print(f"Fetched {rel} -> {local} ({local.stat().st_size} bytes)")
        except Exception as e:
            print(f"MISSING {rel}: {e}")
    sftp.close()

    # Diagnose account3 / account8
    diag_cmds = [
        f"python3 -c \"import json; from pathlib import Path; "
        f"base=Path('{REMOTE}/data'); "
        f"slots=['account3','account8']; "
        f"r={{}}; "
        f"exec('''"
        f"for s in slots:\\n"
        f"  d={{slot:s}}\\n"
        f"  for name in ['cycle_metrics_last.json','groups_health.json','group_send_history.json']:\\n"
        f"    p=base/s/name\\n"
        f"    d[name]=json.loads(p.read_text()) if p.exists() else None\\n"
        f"  cfg=base/'accounts_config.json'\\n"
        f"  ac=json.loads(cfg.read_text()) if cfg.exists() else {{}}\\n"
        f"  d['config']=ac.get(s,{{}})\\n"
        f"  gi=base/'group_intelligence.json'\\n"
        f"  if gi.exists():\\n"
        f"    g=json.loads(gi.read_text())\\n"
        f"    d['health_score']=g.get('accounts',{{}}).get(s,{{}}).get('health_score')\\n"
        f"  r[s]=d\\n"
        f"'''); "
        f"print(json.dumps(r, indent=2))\" 2>&1",

        f"grep -E 'account3|account8' {REMOTE}/data/reload.log 2>/dev/null | tail -20",
        f"pm2 logs telegram-backend --lines 80 --nostream 2>&1 | grep -E 'account3|account8|CYCLE|SKIP|health|unhealthy' | tail -40",
    ]

    print("\n=== ACCOUNT3 / ACCOUNT8 DIAG ===")
    for cmd in diag_cmds[:1]:
        out, err = run(c, cmd, timeout=90)
        print(out or err)

    print("\n=== RECENT LOGS ===")
    for cmd in diag_cmds[1:]:
        out, err = run(c, cmd, timeout=45)
        print(out[:4000] if out else err[:2000])

    # Quick state via curl localhost
    out, _ = run(c,
        "curl -s -u admin:734720077743 http://127.0.0.1:8000/state 2>/dev/null | "
        "python3 -c \"import sys,json; d=json.load(sys.stdin); "
        "ac=d.get('accounts',{}); "
        "for s in ['account3','account8']: "
        "  a=ac.get(s,{}); "
        "  print(s, 'running=',a.get('running'), 'mode=',a.get('output_mode'), "
        "  'success=',a.get('success'), 'health=',a.get('health_score'), "
        "  'skipped=',a.get('skipped'), 'failed=',a.get('failed'), "
        "  'shutdown=',a.get('shutdown_reason'))\" 2>&1",
        timeout=30,
    )
    print("\n=== LIVE STATE ===")
    print(out)

    c.close()

if __name__ == "__main__":
    main()
