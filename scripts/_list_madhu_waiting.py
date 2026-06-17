import json
import os
import sys

import paramiko

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

REMOTE = "/opt/telegramforward.old"
PASSWORD = os.environ.get("VPS_PASSWORD", "")

REMOTE_PY = r'''
import json
import os
import sys
sys.path.insert(0, "/opt/telegramforward.old")
os.chdir("/opt/telegramforward.old")
from dotenv import load_dotenv
load_dotenv("/opt/telegramforward.old/.env", override=False)

from core import ai_smart_reply
from core.dm_store import load_inbox
from core.crm_store import get_lead
from core.ai_smart_reply_store import get_lead_state
from services.crm_service import _unanswered_elapsed_seconds, compute_reply_alert_level

from core.config import ACCOUNTS

out = {"waiting": []}
for slot in ACCOUNTS:
    data = load_inbox(slot)
    for uid, conv in (data.get("conversations") or {}).items():
        msgs = conv.get("messages") or []
        if not msgs or msgs[-1].get("direction") != "in":
            continue
        lead = get_lead(slot, int(uid)) or {}
        elapsed = _unanswered_elapsed_seconds(lead)
        if elapsed is None:
            continue
        ai_state = get_lead_state(slot, int(uid))
        out["waiting"].append({
            "slot": slot,
            "user_id": int(uid),
            "name": conv.get("name"),
            "text": (msgs[-1].get("text") or "")[:80],
            "waiting_sec": int(elapsed),
            "alert": compute_reply_alert_level(lead),
            "ai_enabled": ai_state.get("enabled", True),
            "escalated": ai_state.get("escalated"),
            "disable_reason": ai_state.get("_disable_reason"),
        })

out["waiting"].sort(key=lambda x: -x["waiting_sec"])
out["pending_targets"] = ai_smart_reply.list_pending_inbound_targets()
print(json.dumps(out, indent=2, default=str))
'''

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect("187.127.169.159", username="root", password=PASSWORD, timeout=30)

path = f"{REMOTE}/scripts/_list_madhu_waiting_once.py"
sftp = client.open_sftp()
with sftp.open(path, "w") as f:
    f.write(REMOTE_PY)
sftp.close()

stdin, stdout, stderr = client.exec_command(
    f"cd {REMOTE} && ./venv/bin/python scripts/_list_madhu_waiting_once.py",
    timeout=90,
)
print(stdout.read().decode("utf-8", errors="replace"))
print(stderr.read().decode("utf-8", errors="replace"))
client.close()
