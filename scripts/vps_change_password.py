#!/usr/bin/env python3
"""Find and update dashboard auth password on VPS."""
from __future__ import annotations

import os
import sys

import paramiko

HOST = "187.127.169.159"
USER = "root"
PASSWORD = os.environ.get("VPS_PASSWORD", "")
OLD = "4aN0J41wBk5sPcpodc1JzA"
NEW = "734720077743"
REMOTE_ROOT = "/opt/telegramforward"


def run(cmd: str, timeout: int = 120) -> tuple[str, str, int]:
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(HOST, username=USER, password=PASSWORD, timeout=30)
    _, stdout, stderr = client.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode("utf-8", errors="replace")
    err = stderr.read().decode("utf-8", errors="replace")
    code = stdout.channel.recv_exit_status()
    client.close()
    return out, err, code


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if not PASSWORD:
        raise SystemExit("Set VPS_PASSWORD")

    root, _, _ = run(f"readlink -f {REMOTE_ROOT} 2>/dev/null || echo {REMOTE_ROOT}")
    root = root.strip()
    print(f"Project root: {root}")

    find_cmd = (
        f"grep -rl '{OLD}' {root} /opt/telegramforward* 2>/dev/null "
        f"| grep -v node_modules | grep -v '.git/' | head -20"
    )
    out, err, code = run(find_cmd)
    files = [ln.strip() for ln in out.splitlines() if ln.strip()]
    print("Files containing old password:")
    for f in files:
        print(f"  {f}")

    if not files:
        # Also search env var names
        env_cmd = (
            f"grep -rE 'DASHBOARD|AUTH_PASSWORD|ADMIN_PASSWORD|dashboard_password' "
            f"{root}/.env {root}/data 2>/dev/null | head -20"
        )
        out2, _, _ = run(env_cmd)
        print("Auth-related env/config:")
        print(out2 or "(none found)")
        raise SystemExit("Old password not found on VPS")

    for path in files:
        sed_cmd = (
            f"sed -i 's/{OLD}/{NEW}/g' '{path}' && echo 'updated: {path}'"
        )
        uout, uerr, ucode = run(sed_cmd)
        print(uout.strip() or uerr.strip())
        if ucode != 0:
            raise SystemExit(f"Failed updating {path}")

    verify, _, _ = run(f"grep -rl '{NEW}' {root} 2>/dev/null | head -5")
    print("Verified in:", verify.strip())

    print("Restarting backend...")
    rout, rerr, rcode = run("pm2 restart telegram-backend 2>&1; sleep 2; curl -sf http://127.0.0.1:8000/health && echo OK")
    print(rout)
    if rcode != 0:
        print(rerr, file=sys.stderr)
        raise SystemExit(rcode)
    print("Done.")


def verify_login() -> None:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if not PASSWORD:
        raise SystemExit("Set VPS_PASSWORD")
    cmd = (
        "grep -E 'PASSWORD|AUTH' /opt/telegramforward.old/.env | sed 's/=.*/=***/'; "
        "pm2 restart telegram-backend --update-env; sleep 3; "
        f"curl -s -X POST http://127.0.0.1:8000/auth/login "
        f"-H 'Content-Type: application/json' "
        f"-d '{{\"username\":\"admin\",\"password\":\"{NEW}\"}}' -c /tmp/cookies.txt; echo; "
        "curl -s http://127.0.0.1:8000/auth/status -b /tmp/cookies.txt"
    )
    out, err, code = run(cmd, timeout=90)
    print(out)
    if err.strip():
        print(err, file=sys.stderr)
    if code != 0:
        raise SystemExit(code)


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "verify":
        verify_login()
    else:
        main()

