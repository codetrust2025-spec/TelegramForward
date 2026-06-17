"""One-shot WhatsApp CRM verification on VPS (run locally with VPS_PASSWORD set)."""
from __future__ import annotations

import json
import os
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HOST = "187.127.169.159"
REMOTE = "/opt/telegramforward"
PY = f"{REMOTE}/venv/bin/python"


def main() -> int:
    pwd = os.environ.get("VPS_PASSWORD", "")
    if not pwd:
        print("VPS_PASSWORD not set", file=sys.stderr)
        return 1

    import paramiko

    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(HOST, username="root", password=pwd, timeout=30)

    inject = (
        f"cd {REMOTE} && PYTHONPATH={REMOTE} {PY} -c \""
        "from dotenv import load_dotenv; load_dotenv('/opt/telegramforward/.env'); "
        "import asyncio, json; "
        "from services.whatsapp_inbox_service import process_webhook_payload; "
        "payload = {'type': 'message_received', 'data': {"
        "'customer': {'phone_number': '919876543210', 'name': 'WA Deploy Test'}, "
        "'message': {'id': 'deploy_test_verify', 'message_type': 'text', "
        "'text': 'Hello from deploy verification'}}}; "
        "print(json.dumps(asyncio.run(process_webhook_payload(payload))))\""
    )
    _, o, e = client.exec_command(inject, timeout=60)
    print("Inject:", (o.read() + e.read()).decode().strip())

    checks = (
        f"curl -s http://127.0.0.1:8000/whatsapp/status; echo; "
        f"grep -c wa_media_store {REMOTE}/core/wa_media_store.py; "
        f"grep -c wa-media {REMOTE}/core/whatsapp_api.py; "
        f"grep -o '2026-06-05-whatsapp-full' {REMOTE}/static/assets/app-*.js | head -1"
    )
    _, o2, _ = client.exec_command(checks, timeout=30)
    print("Checks:", o2.read().decode().strip())

    client.close()
    print("\nOK — open https://teleautomation.online Inbox → account1 → WA Deploy Test")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
