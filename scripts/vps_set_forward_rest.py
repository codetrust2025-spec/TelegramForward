#!/usr/bin/env python3
"""Set forward rest window on VPS and restart backend."""
from __future__ import annotations

import socket
import sys

import paramiko

HOST = "187.127.169.159"
USER = "root"
PASSWORD = "REMOVED_VPS_PASSWORD"
REMOTE_ROOT = "/opt/telegramforward.old"
MIN_SECONDS = 480   # 8 min
MAX_SECONDS = 1200  # 20 min


def run(client: paramiko.SSHClient, cmd: str, timeout: int = 120) -> tuple[str, str, int]:
    _, stdout, stderr = client.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode("utf-8", errors="replace")
    err = stderr.read().decode("utf-8", errors="replace")
    code = stdout.channel.recv_exit_status()
    return out, err, code


def upsert_env_line(text: str, key: str, value: str) -> str:
    lines = text.splitlines()
    found = False
    out: list[str] = []
    for line in lines:
        if line.strip().startswith(f"{key}="):
            out.append(f"{key}={value}")
            found = True
        else:
            out.append(line)
    if not found:
        if out and out[-1].strip():
            out.append("")
        out.append(f"# Forward tick rest between bursts (seconds)")
        out.append(f"{key}={value}")
    return "\n".join(out).rstrip() + "\n"


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sock = socket.create_connection((HOST, 22), timeout=30)
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(hostname=HOST, username=USER, password=PASSWORD, sock=sock)

    root_out, _, _ = run(client, f"readlink -f /opt/telegramforward 2>/dev/null || echo {REMOTE_ROOT}")
    root = root_out.strip() or REMOTE_ROOT
    env_path = f"{root}/.env"
    print(f"Using {env_path}")

    read_out, read_err, read_code = run(client, f"cat '{env_path}'")
    if read_code != 0:
        raise SystemExit(f"Failed to read .env: {read_err or read_out}")

    updated = upsert_env_line(read_out, "FORWARD_REST_MIN_SECONDS", str(MIN_SECONDS))
    updated = upsert_env_line(updated, "FORWARD_REST_MAX_SECONDS", str(MAX_SECONDS))

    # Write via heredoc to avoid escaping issues
    escaped = updated.replace("'", "'\"'\"'")
    write_cmd = f"cat > '{env_path}' <<'EOFENV'\n{updated}EOFENV"
    _, write_err, write_code = run(client, write_cmd)
    if write_code != 0:
        raise SystemExit(f"Failed to write .env: {write_err}")

    verify_out, _, _ = run(
        client,
        f"grep -E '^FORWARD_REST_(MIN|MAX)_SECONDS=' '{env_path}'",
    )
    print("Updated .env:")
    print(verify_out.strip())

    print("Restarting telegram-backend...")
    restart_out, restart_err, restart_code = run(
        client,
        "pm2 restart telegram-backend --update-env 2>&1; sleep 3; "
        "curl -sf http://127.0.0.1:8000/health && echo ' health OK' || echo ' health check failed'",
        timeout=90,
    )
    print(restart_out.strip())
    if restart_code != 0:
        print(restart_err, file=sys.stderr)
        raise SystemExit(restart_code)

    check_script = f"""
import os
from pathlib import Path
for line in Path('{env_path}').read_text().splitlines():
    if line.startswith('FORWARD_REST'):
        k,v = line.split('=',1)
        os.environ[k] = v
from importlib import reload
import core.posting_mode as pm
reload(pm)
print('pick_forward_rest range:', pm.FORWARD_REST_MIN_SECONDS, '-', pm.FORWARD_REST_MAX_SECONDS)
sample = [pm.pick_forward_rest_seconds() for _ in range(5)]
print('sample picks:', sample)
"""
    check_out, check_err, check_code = run(
        client,
        f"cd '{root}' && set -a && . ./.env && set +a && PYTHONPATH=. ./venv/bin/python - <<'PY'\n{check_script}\nPY",
        timeout=60,
    )
    print(check_out.strip())
    if check_code != 0 and check_err.strip():
        print(check_err.strip())

    client.close()
    print(f"\nDone. Forward rest is now {MIN_SECONDS // 60}–{MAX_SECONDS // 60} minutes between ticks.")


if __name__ == "__main__":
    main()
