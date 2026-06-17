"""More VPS Karthik diagnostics."""
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

    print("=== dm_inbox ai hooks ===")
    print(run(f"grep -n 'maybe_schedule\\|ai_smart' {REMOTE}/services/dm_inbox_service.py 2>/dev/null | sed -n '1,25p'"))

    print("\n=== karthik_inbox_sweep.py (first 130 lines) ===")
    print(run(f"sed -n '1,130p' {REMOTE}/core/karthik_inbox_sweep.py"))

    print("\n=== sweep references ===")
    print(run(f"grep -rn 'karthik_inbox_sweep\\|inbox_sweep' {REMOTE} --include='*.py' | sed -n '1,30p'"))

    print("\n=== work_hours config ===")
    print(run(
        f"python3 -c \"import json; c=json.load(open('{REMOTE}/data/ai_smart_reply.json'))['config']; "
        "print('work_hours', c.get('work_hours')); print('mode', c.get('mode')); print('enabled', c.get('enabled'))\""
    ))

    print("\n=== account worker AI_AUTO_REPLY ===")
    print(run(f"grep -n 'AI_AUTO\\|generate_and_send' {REMOTE}/workers/account_worker.py {REMOTE}/messaging/task_types.py 2>/dev/null | sed -n '1,30p'"))

    print("\n=== pm2 logs tail ===")
    print(run("pm2 logs telegram-backend --nostream --lines 150 2>/dev/null | tail -60"))

    print("\n=== trigger catch_up via pm2 python ===")
    print(run(
        f"cd {REMOTE} && PYTHONPATH={REMOTE} /usr/bin/env -i HOME=/root PATH=/usr/local/bin:/usr/bin:/bin "
        f"$(pm2 env 0 2>/dev/null | grep -m1 '^PATH=' || echo PATH=/usr/bin) "
        f"python3 -c 'import asyncio; from core.ai_smart_reply import catch_up_pending_replies, health; "
        f"print(health()); print(asyncio.run(catch_up_pending_replies(max_replies=5)))' 2>&1 | sed -n '1,40p'"
    ))

    ssh.close()


if __name__ == "__main__":
    main()
