"""VPS: sweep startup + login_exclusive inversion check."""
from __future__ import annotations

import os
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HOST = "187.127.169.159"
USER = "root"
REMOTE = "/opt/telegramforward"
PASSWORD = os.environ.get("VPS_PASSWORD", "")


def main() -> None:
    import paramiko

    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(HOST, username=USER, password=PASSWORD, timeout=30)

    def run(cmd: str) -> str:
        _, stdout, stderr = ssh.exec_command(cmd, timeout=120)
        return (stdout.read() + stderr.read()).decode("utf-8", errors="replace")

    print("=== sweep.start callers ===")
    print(run(f"grep -rn 'karthik_inbox_sweep' {REMOTE} --include='*.py'"))

    print("\n=== any_login_exclusive ===")
    print(run(f"grep -n 'def any_login_exclusive' -A30 {REMOTE}/core/telegram_client.py"))

    print("\n=== account_worker ai handler ===")
    print(run(f"grep -n 'AI_AUTO\\|ai_auto\\|generate_and_send' {REMOTE}/workers/account_worker.py"))

    print("\n=== pm2 interpreter + sweep in process ===")
    print(run("pm2 describe telegram-backend 2>/dev/null | grep -E 'exec cwd|interpreter|script path'"))
    print(run(
        f"cd {REMOTE} && PYTHONPATH={REMOTE} $(pm2 jlist 2>/dev/null | python3 -c "
        "\"import sys,json; p=json.load(sys.stdin)[0]; print(p.get('pm_exec_path',''))\" 2>/dev/null || echo python3) "
        "-c 'pass' 2>&1 || true"
    ))

    ssh.close()


if __name__ == "__main__":
    main()
