"""Diagnose why Karthik auto-reply is not firing on VPS."""
from __future__ import annotations

import json
import os
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HOST = "187.127.169.159"
USER = "root"
REMOTE = "/opt/telegramforward"
PASSWORD = os.environ.get("VPS_PASSWORD", "")


def run(ssh, cmd: str) -> str:
    _, stdout, stderr = ssh.exec_command(cmd, timeout=120)
    out = stdout.read().decode("utf-8", errors="replace")
    err = stderr.read().decode("utf-8", errors="replace")
    return (out + err).strip()


def main() -> None:
    import paramiko

    if not PASSWORD:
        print("Set VPS_PASSWORD")
        sys.exit(1)

    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(HOST, username=USER, password=PASSWORD, timeout=30)

    print("=== grep maybe_schedule / enqueue_ai ===")
    print(run(ssh, f"grep -rn 'maybe_schedule_ai_reply\\|enqueue_ai_auto_reply' {REMOTE} --include='*.py' | head -40"))

    print("\n=== AI health via curl ===")
    print(run(ssh, "curl -s http://127.0.0.1:8000/ai/smart-reply/config 2>/dev/null | python3 -m json.tool 2>/dev/null | head -80"))

    print("\n=== ai_smart_reply.json config keys ===")
    print(run(ssh, f"python3 -c \"import json; d=json.load(open('{REMOTE}/data/ai_smart_reply.json')); c=d.get('config',{{}}); print('enabled',c.get('enabled')); print('mode',c.get('mode')); print('api_key check via health only'); print('require_assessment',c.get('require_assessment')); la=c.get('last_assessment') or {{}}; print('assessment_verdict',la.get('verdict')); print('manual_approval',c.get('manual_approval_at'))\""))

    print("\n=== OPENAI / AI env present? ===")
    print(run(ssh, "grep -E '^(AI_|OPENAI_)' /opt/telegramforward/.env 2>/dev/null | sed 's/=.*/=***/' || echo 'no .env keys'"))

    print("\n=== PM2 logs ai_smart / skip (last 80) ===")
    print(run(ssh, "pm2 logs telegram-backend --nostream --lines 200 2>/dev/null | grep -iE 'ai_smart|ai_skipped|skip schedule|llm_error|assessment|catch_up|inbox_sweep|enqueue' | tail -80"))

    print("\n=== pending inbound count ===")
    print(run(ssh, f"cd {REMOTE} && PYTHONPATH={REMOTE} python3 -c \"from core.ai_smart_reply import list_pending_inbound_targets, health; print('pending',len(list_pending_inbound_targets())); print(health())\""))

    ssh.close()


if __name__ == "__main__":
    main()
