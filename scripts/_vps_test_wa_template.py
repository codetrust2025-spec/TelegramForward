"""Probe Interakt template send for a lead (local runner with VPS_PASSWORD)."""
from __future__ import annotations

import json
import os
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HOST = "187.127.169.159"
REMOTE = "/opt/telegramforward"
PY = f"{REMOTE}/venv/bin/python"

SLOT = os.environ.get("WA_TEST_SLOT", "account9")
USER_ID = os.environ.get("WA_TEST_USER", "8944100819")
PHONE = os.environ.get("WA_TEST_PHONE", "918639074573")


def main() -> int:
    pwd = os.environ.get("VPS_PASSWORD", "")
    if not pwd:
        print("VPS_PASSWORD not set", file=sys.stderr)
        return 1

    import paramiko

    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(HOST, username="root", password=pwd, timeout=30)

    probe = (
        f"cd {REMOTE} && PYTHONPATH={REMOTE} {PY} <<'PYEOF'\n"
        "from dotenv import load_dotenv\n"
        "load_dotenv('/opt/telegramforward/.env')\n"
        "import asyncio, json\n"
        "from services.whatsapp_interakt import InteraktClient\n"
        "from services.whatsapp_send_service import resolve_phone_for_lead, send_template\n"
        f"slot, uid = '{SLOT}', int('{USER_ID}')\n"
        f"phone = resolve_phone_for_lead(slot, uid) or '{PHONE}'\n"
        "print('resolved_phone', phone)\n"
        "client = InteraktClient()\n"
        "async def run():\n"
        "    direct = await client.send_template(phone, 'whatsapp_move_from_telegram', ['Vani Sree', 'interview support'])\n"
        "    print('interakt_direct', json.dumps(direct, default=str))\n"
        "    wrapped = await send_template(slot, uid, 'whatsapp_move_from_telegram', ['Vani Sree', 'interview support'])\n"
        "    print('send_template', json.dumps(wrapped, default=str))\n"
        "asyncio.run(run())\n"
        "PYEOF"
    )
    _, o, e = client.exec_command(probe, timeout=90)
    print((o.read() + e.read()).decode())

    _, o2, _ = client.exec_command(
        "pm2 logs telegram-backend --nostream --lines 80 2>/dev/null | grep -iE 'Interakt|template' | tail -15",
        timeout=20,
    )
    print("--- logs ---")
    print(o2.read().decode())
    client.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
