"""Diagnose why Karthik did not reply to BG lead."""
from __future__ import annotations

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

    probe = """cd {REMOTE} && PYTHONPATH={REMOTE} {PY} <<'PYEOF'
from dotenv import load_dotenv
load_dotenv('{REMOTE}/.env')
from core import ai_smart_reply
from core.ai_smart_reply_store import get_config, get_lead_state
from core.dm_store import load_inbox
from core.config import ACCOUNTS
from core.crm_store import get_lead
from services.account_manager import manager

cfg = get_config()
print("AI_ENABLED", cfg.get("enabled"))
print("AI_MODE", cfg.get("mode"))
print("DELAY", cfg.get("min_delay_seconds"), cfg.get("max_delay_seconds"))
try:
    print("HEALTH", ai_smart_reply.health())
except Exception as e:
    print("HEALTH_ERROR", repr(e))

hits = []
for slot in ACCOUNTS:
    for k, conv in (load_inbox(slot).get("conversations") or {}).items():
        name = (conv.get("name") or "").strip()
        if name.upper() == "BG" or str(k) == "1234875138":
            try:
                uid = int(conv.get("user_id") or k)
            except (TypeError, ValueError):
                continue
            hits.append((slot, uid, conv))

for slot, uid, conv in hits:
    lead = get_lead(slot, uid) or {}
    st = get_lead_state(slot, uid)
    rt = manager.get_runtime(slot)
    w = rt.worker.state
    print("LEAD", slot, uid, conv.get("name"), "unread", conv.get("unread_count"))
    print("WORKER running", w.running, "logged_in", bool(w.account_info and w.account_info.get("phone")))
    print("QUEUE", rt.queue.status_dict())
    print("CRM", lead.get("status"), "last_reply_at", lead.get("last_reply_at"))
    keys = ("enabled", "escalated", "_disable_reason", "stage", "last_user_message_id",
            "reply_count_today", "ai_lock_reason")
    print("STATE", dict((k, st.get(k)) for k in keys if st.get(k) is not None))
    msgs = conv.get("messages") or []
    for m in msgs[-6:]:
        print(" MSG", m.get("direction"), repr((m.get("text") or "")[:60]), m.get("sent_by"), m.get("id"))
    last_in = next((m for m in reversed(msgs) if m.get("direction") == "in"), None)
    if last_in:
        print("LAST_IN_ID", last_in.get("id"), "ts", last_in.get("timestamp"))

if not hits:
    print("NO_BG_LEAD_FOUND")
else:
    import asyncio
    import urllib.request
    import json
    try:
        req = urllib.request.Request(
            "http://127.0.0.1:8000/ai/smart-reply/catch-up",
            data=json.dumps({"slot": "account9", "max_replies": 3, "force": True}).encode(),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=120) as resp:
            print("CATCH_UP_API", resp.read().decode()[:2000])
    except Exception as e:
        print("CATCH_UP_API_ERROR", repr(e))
    import time
    time.sleep(25)
    conv = (load_inbox("account9").get("conversations") or {}).get("1234875138") or {}
    for m in (conv.get("messages") or [])[-4:]:
        print(" AFTER", m.get("direction"), repr((m.get("text") or "")[:80]), m.get("sent_by"))
PYEOF
""".replace("{REMOTE}", REMOTE).replace("{PY}", PY)
    _, o, e = client.exec_command(probe, timeout=60)
    print((o.read() + e.read()).decode())

    _, o2, _ = client.exec_command(
        "pm2 logs telegram-backend --nostream --lines 120 2>/dev/null | "
        "grep -i ai_smart_reply | tail -20",
        timeout=20,
    )
    print("--- recent ai logs ---")
    print(o2.read().decode())

    _, o3, _ = client.exec_command(
        f"grep -E 'AI_API_KEY|OPENAI' {REMOTE}/.env | sed 's/=.*/=***/'",
        timeout=10,
    )
    print("--- ai env ---")
    print(o3.read().decode())

    client.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
