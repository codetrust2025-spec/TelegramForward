"""Quick production Karthik health check."""
from __future__ import annotations

import os
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HOST = "187.127.169.159"
USER = "root"
REMOTE = "/opt/telegramforward.old"
PASSWORD = os.environ.get("VPS_PASSWORD", "")


def run(ssh, cmd: str) -> str:
    _, stdout, stderr = ssh.exec_command(cmd, timeout=120)
    return (stdout.read() + stderr.read()).decode("utf-8", errors="replace").strip()


def main() -> int:
    import paramiko

    if not PASSWORD:
        print("VPS_PASSWORD not set")
        return 1

    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(HOST, username=USER, password=PASSWORD, timeout=30)

    py = (
        f"import json, os\n"
        f"os.chdir('{REMOTE}')\n"
        f"import sys\n"
        f"sys.path.insert(0, '{REMOTE}')\n"
        f"from core.ai_smart_reply import health, is_enabled, list_pending_inbound_targets\n"
        f"from core.ai_smart_reply_store import get_config\n"
        f"c = get_config()\n"
        f"print('is_enabled', is_enabled())\n"
        f"print('config_enabled', c.get('enabled'))\n"
        f"print('mode', c.get('mode'))\n"
        f"print('work_hours_enabled', c.get('work_hours_enabled'))\n"
        f"print('api_key_env', bool(os.getenv('AI_API_KEY') or os.getenv('OPENAI_API_KEY')))\n"
        f"d = json.load(open('data/ai_smart_reply.json'))\n"
        f"leads = d.get('leads') or {{}}\n"
        f"off = [k for k,v in leads.items() if not v.get('enabled', True)]\n"
        f"esc = [k for k,v in leads.items() if v.get('escalated')]\n"
        f"sticky = [k for k,v in leads.items() if (v.get('_disable_reason') or '') in "
        f"('user_opt_out','human_owned','manual','service_complaint')]\n"
        f"print('leads_disabled', len(off), off[:6])\n"
        f"print('leads_escalated', len(esc))\n"
        f"print('leads_sticky_lock', len(sticky), sticky[:6])\n"
        f"pending = list_pending_inbound_targets()\n"
        f"print('pending_inbound', len(pending))\n"
        f"if pending[:3]:\n"
        f"    print('sample_pending', pending[:3])\n"
        f"print('health', health())\n"
    )
    print("=== Karthik production ===")
    print(run(ssh, f"cd {REMOTE} && PYTHONPATH={REMOTE} python3 -c {repr(py)}"))

    print("\n=== PM2 / workers snippet ===")
    print(run(ssh, "pm2 jlist 2>/dev/null | python3 -c \"import sys,json; d=json.load(sys.stdin); p=d[0] if d else {}; print('status',p.get('pm2_env',{}).get('status')); print('restarts',p.get('pm2_env',{}).get('restart_time'))\" 2>/dev/null || pm2 status"))

    print("\n=== Recent AI log lines ===")
    print(run(ssh, "pm2 logs telegram-backend --nostream --lines 300 2>/dev/null | grep -iE 'ai_smart|skip schedule|human_active|human_owned|ai_disabled|llm_error|enqueue|karthik' | tail -25"))

    ssh.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
