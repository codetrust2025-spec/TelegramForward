#!/usr/bin/env python3
"""Investigate shutdown list root cause on VPS."""
from __future__ import annotations

import json
import os
import sys

import paramiko

HOST = "187.127.169.159"
USER = "root"
PASSWORD = os.environ.get("VPS_PASSWORD", "")
ROOT = "/opt/telegramforward.old"
SLOTS = ["account1", "account2", "account4", "account8"]


def run(cmd: str, timeout: int = 180) -> str:
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(HOST, username=USER, password=PASSWORD, timeout=30)
    _, stdout, stderr = c.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode("utf-8", errors="replace")
    err = stderr.read().decode("utf-8", errors="replace")
    code = stdout.channel.recv_exit_status()
    c.close()
    if code != 0 and not out.strip():
        raise RuntimeError(f"exit {code}: {err[:2000]}")
    return out + (f"\n[stderr]\n{err}" if err.strip() else "")


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if not PASSWORD:
        raise SystemExit("Set VPS_PASSWORD")

    sections = []

    sections.append("=== GREP SHUTDOWN CODE ===")
    sections.append(
        run(
            f"grep -rn 'shutdown\\|SHUTDOWN\\|shutdown_list\\|account_shutdown' "
            f"{ROOT} --include='*.py' 2>/dev/null | grep -v __pycache__ | head -80"
        )
    )

    sections.append("=== GREP THRESHOLDS 12h/7d ===")
    sections.append(
        run(
            f"grep -rn '43200\\|604800\\|12 \\* 3600\\|7 \\* 24\\|timedelta.*12\\|timedelta.*7\\|hours=12\\|days=7' "
            f"{ROOT} --include='*.py' 2>/dev/null | head -40"
        )
    )

    sections.append("=== SHUTDOWN FUNCTION DEFINITIONS ===")
    sections.append(
        run(
            f"grep -rn 'def .*shutdown\\|class .*Shutdown' {ROOT} --include='*.py' 2>/dev/null"
        )
    )

    sections.append("=== .env SHUTDOWN CONFIG ===")
    sections.append(run(f"grep -i shutdown {ROOT}/.env 2>/dev/null || echo '(none)'"))

    sections.append("=== CURRENT /state SHUTDOWN FIELDS ===")
    sections.append(
        run(
            "curl -s http://127.0.0.1:8000/state -b /tmp/cookies.txt 2>/dev/null | "
            "python3 -c \"import sys,json; d=json.load(sys.stdin); "
            "print(json.dumps({k:d.get(k) for k in ['account_shutdown','shutdown_list','account_info','account_states','account_status'] if k in d}, indent=2))\" "
            "2>/dev/null || curl -s http://127.0.0.1:8000/state | head -c 5000"
        )
    )

    sections.append("=== LOGIN + STATE ===")
    sections.append(
        run(
            "curl -s -X POST http://127.0.0.1:8000/auth/login "
            "-H 'Content-Type: application/json' "
            "-d '{\"username\":\"admin\",\"password\":\"734720077743\"}' -c /tmp/cookies.txt; echo; "
            "curl -s http://127.0.0.1:8000/state -b /tmp/cookies.txt | "
            "python3 - <<'PY'\n"
            "import json,sys\n"
            "d=json.load(sys.stdin)\n"
            "slots=['account1','account2','account4','account8']\n"
            "out={}\n"
            "for s in slots:\n"
            "  out[s]={\n"
            "    'info': (d.get('account_info') or {}).get(s),\n"
            "    'shutdown': (d.get('account_shutdown') or {}).get(s),\n"
            "    'shutdown_list': (d.get('shutdown_list') or {}).get(s),\n"
            "    'status': (d.get('account_status') or {}).get(s),\n"
            "    'state': (d.get('account_states') or {}).get(s),\n"
            "  }\n"
            "print(json.dumps(out, indent=2))\n"
            "PY"
        )
    )

    sections.append("=== DATA FILES SHUTDOWN ===")
    sections.append(
        run(
            f"find {ROOT}/data -maxdepth 2 -type f \\( -name '*shutdown*' -o -name '*rest*' \\) 2>/dev/null; "
            f"grep -rl 'shutdown' {ROOT}/data 2>/dev/null | head -20"
        )
    )

    sections.append("=== POSTGRES TABLES ===")
    sections.append(
        run(
            f"grep -i 'DATABASE\\|POSTGRES' {ROOT}/.env | sed 's/=.*/=***/'; "
            f"python3 - <<'PY'\n"
            "import os, re\n"
            "from pathlib import Path\n"
            "env = {}\n"
            f"for line in Path('{ROOT}/.env').read_text().splitlines():\n"
            "  if '=' in line and not line.strip().startswith('#'):\n"
            "    k,v=line.split('=',1); env[k.strip()]=v.strip().strip('\"')\n"
            "url = env.get('DATABASE_URL') or env.get('POSTGRES_URL') or ''\n"
            "print('DB url present:', bool(url))\n"
            "if url:\n"
            "  try:\n"
            "    import psycopg2\n"
            "    conn = psycopg2.connect(url)\n"
            "    cur = conn.cursor()\n"
            "    cur.execute(\"SELECT tablename FROM pg_tables WHERE schemaname='public' ORDER BY 1\")\n"
            "    print('tables:', [r[0] for r in cur.fetchall()])\n"
            "    for t in ['account_shutdown','shutdown','daily_stats','send_stats','account_state']:\n"
            "      cur.execute(\"SELECT tablename FROM pg_tables WHERE tablename LIKE %s\", (f'%'+t+'%',))\n"
            "      print(t, cur.fetchall())\n"
            "    conn.close()\n"
            "  except Exception as e:\n"
            "    print('pg error:', e)\n"
            "PY"
        )
    )

    sections.append("=== PM2 LOGS SHUTDOWN (last 200 lines) ===")
    sections.append(
        run(
            "pm2 logs telegram-backend --lines 500 --nostream 2>&1 | "
            "grep -i 'shutdown\\|account1\\|account2\\|account4\\|account8\\|12 hour\\|7 day\\|no successful' | tail -80"
        )
    )

    out_path = os.path.join(os.environ.get("TEMP", "."), "shutdown_investigation_output.txt")
    text = "\n\n".join(sections)
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(text)
    print(text)
    print(f"\n=== Saved to {out_path} ===")


if __name__ == "__main__":
    main()
