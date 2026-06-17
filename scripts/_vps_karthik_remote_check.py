import json
import os
import sys

os.chdir("/opt/telegramforward.old")
sys.path.insert(0, "/opt/telegramforward.old")

from core.ai_smart_reply import health, is_enabled, list_pending_inbound_targets
from core.ai_smart_reply_store import get_config

c = get_config()
print("is_enabled", is_enabled())
print("config_enabled", c.get("enabled"))
print("mode", c.get("mode"))
print("work_hours_enabled", c.get("work_hours_enabled"))
print("api_key_env", bool(os.getenv("AI_API_KEY") or os.getenv("OPENAI_API_KEY")))
print("api_base", os.getenv("AI_API_BASE_URL") or os.getenv("OPENAI_BASE_URL") or "default-openai")

d = json.load(open("data/ai_smart_reply.json"))
leads = d.get("leads") or {}
off = [k for k, v in leads.items() if not v.get("enabled", True)]
esc = [k for k, v in leads.items() if v.get("escalated")]
sticky = [
    k for k, v in leads.items()
    if (v.get("_disable_reason") or "") in (
        "user_opt_out", "human_owned", "manual", "service_complaint",
    )
]
print("leads_disabled", len(off))
print("leads_escalated", len(esc))
print("leads_sticky_lock", len(sticky))
if sticky[:8]:
    print("sticky_sample", sticky[:8])

pending = list_pending_inbound_targets()
print("pending_inbound", len(pending))
if pending[:5]:
    for t in pending[:5]:
        print(" pending", t.get("slot"), t.get("user_id"), (t.get("text") or "")[:60])

h = health()
print("health_enabled", h.get("enabled"))
print("health_api_key", h.get("api_key_present"))
print("health_pending", h.get("pending_inbound"))
print("health_model", h.get("model"))
if h.get("inbox_sweep"):
    print("inbox_sweep", h.get("inbox_sweep"))
if h.get("llm_gateway"):
    print("llm_gateway", h.get("llm_gateway"))
