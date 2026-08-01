"""Auto-extracted ai routes (pure move from server.py)."""
import asyncio
import json
import logging
import os
import shutil
from datetime import datetime
from fastapi import Body, Depends, FastAPI, File, Form, HTTPException, Query, Request, Response, UploadFile, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from core import broadcast
from core.config import ACCOUNTS, ACCOUNT_SLOTS, BASE_DIR, DATA_DIR, GROUPS_FILE, MESSAGE_FILE
from core.groups_store import (
    _normalize_group_name,
    build_group_lists,
    collect_all_dead_for_upload,
    ensure_groups_loaded,
    ensure_invalid_registry_backfill,
    is_valid_group_username,
    load_account_dead,
    load_master_groups,
    normalize_upload_username,
    save_master_groups,
)
from core.config import MESSAGE_REWRITE_ENABLED
from core.message_rewrite import preview_cycle_message
from core.message_store import (
    load_message,
    load_message_for_account,
    save_message,
    save_message_for_account,
)
from core import telegram_client
from telethon import TelegramClient
from core.account_info_store import (
    clear_account_info,
    duplicate_phone_login_message,
    find_logged_in_slot_by_phone,
    load_account_info,
    save_account_info,
)
from core.login_pending import clear_pending, load_pending, save_pending
from core.worker_persistence import log_reload_event
from services.account_manager import manager
from events.event_bus import event_bus
from events.event_types import EventType
from core.admin_dashboard import install_admin_dashboard
from core.dashboard_auth_api import install_dashboard_auth
from core.voice_call_api import install_voice_call_routes
from core.web_push_api import install_web_push_routes
from core.whatsapp_api import install_whatsapp_routes
from core.public_slot_api import install_public_slot_routes
from core.demo_tools_api import install_demo_tools_routes
from core.recruitment_mail_api import install_recruitment_mail_routes
from fastapi import APIRouter
from server import (
    _viewer_reference,
)

router = APIRouter()
logger = logging.getLogger(__name__)


def _smart_reply_health() -> dict:
    """Health block for the settings screen, degrading instead of failing.

    ``core.ai_smart_reply`` imports the Karthik playbook tree, which lives
    outside git (see core/ai_smart_reply_store.py). Deployments without that
    tree cannot import the module at all, and a hard import here turned the
    whole settings endpoint into a 500 — taking every unrelated control on that
    screen down with it, including the OCR switch. Report the module as
    unavailable instead; the caller still gets its config.
    """
    try:
        from core import ai_smart_reply

        health = ai_smart_reply.health()
        health.setdefault("available", True)
        return health
    except Exception as exc:  # noqa: BLE001 - degraded health must never raise
        logger.warning("AI smart reply health unavailable: %s", exc)
        return {
            "available": False,
            "enabled": False,
            "api_key_present": bool(
                (os.getenv("AI_API_KEY") or os.getenv("OPENAI_API_KEY") or "").strip()
            ),
            "unavailable_reason": (
                "The AI smart reply engine is not installed on this deployment, "
                "so its status and controls cannot be read."
            ),
        }


@router.get("/ai/smart-reply/config")
async def ai_smart_reply_get_config():
    from core.ai_smart_reply_store import get_config

    return {
        "status": "ok",
        "config": get_config(),
        "health": _smart_reply_health(),
    }
@router.post("/ai/smart-reply/config")
async def ai_smart_reply_update_config(body: dict):
    from core.ai_smart_reply_store import update_config

    patch = {k: v for k, v in (body or {}).items() if v is not None}
    cfg = update_config(**patch)
    return {
        "status": "ok",
        "config": cfg,
        "health": _smart_reply_health(),
    }
@router.get("/ai/smart-reply/preset/economy")
async def ai_smart_reply_economy_preset_preview():
    from core.karthik_economy_preset import economy_preset_preview

    return {
        "status": "ok",
        "preview": economy_preset_preview(replace_business_prompt=True),
        "estimated_monthly_usd": "15-22",
    }
@router.post("/ai/smart-reply/preset/economy")
async def ai_smart_reply_apply_economy_preset(body: dict | None = None):
    from core import ai_smart_reply
    from core.karthik_economy_preset import apply_economy_preset

    body = body or {}
    replace_prompt = body.get("replace_business_prompt", True)
    if isinstance(replace_prompt, str):
        replace_prompt = replace_prompt.strip().lower() in {"1", "true", "yes"}
    cfg = apply_economy_preset(replace_business_prompt=bool(replace_prompt))
    return {
        "status": "ok",
        "config": cfg,
        "health": ai_smart_reply.health(),
        "message": "Economy preset applied — lower caps, group rewrite off, compact master prompt.",
    }
@router.post("/ai/smart-reply/preset/standard-caps")
async def ai_smart_reply_apply_standard_caps_preset():
    from core import ai_smart_reply
    from core.karthik_economy_preset import apply_standard_caps_preset

    cfg = apply_standard_caps_preset()
    return {
        "status": "ok",
        "config": cfg,
        "health": ai_smart_reply.health(),
        "message": "Standard caps restored (master prompt unchanged).",
    }
@router.post("/ai/smart-reply/catch-up")
async def ai_smart_reply_catch_up(body: dict | None = None):
    """Enqueue Karthik replies for all waiting inbound chats (after outages)."""
    from core import ai_smart_reply

    if not ai_smart_reply.is_enabled():
        return {"status": "error", "message": "AI disabled or API key missing"}
    body = body or {}
    slot = (body.get("slot") or "").strip() or None
    if slot and slot not in ACCOUNTS:
        return {"status": "error", "message": "Invalid slot"}
    max_replies = int(body.get("max_replies") or 25)
    result = await ai_smart_reply.catch_up_pending_replies(
        slot=slot,
        force=bool(body.get("force", True)),
        max_replies=max_replies,
    )
    return {"status": "ok", **result}
@router.post("/ai/smart-reply/leads/{slot}/{user_id}/toggle")
async def ai_smart_reply_lead_toggle(slot: str, user_id: int, body: dict):
    """Enable / disable AI auto-reply for a single lead, or reset its stage."""
    if slot not in ACCOUNTS:
        return {"status": "error", "message": "Invalid slot"}
    from core import ai_smart_reply
    from core.ai_smart_reply_store import (
        STAGE_GREETING,
        get_lead_state,
        update_lead_state,
    )

    if "enabled" in (body or {}):
        enabled = bool(body.get("enabled"))
        if enabled:
            state = ai_smart_reply.enable_for_lead(slot, int(user_id))
        else:
            state = ai_smart_reply.disable_for_lead(slot, int(user_id), reason="ui_toggle")
        return {"status": "ok", "lead_state": state}

    if body.get("reset_stage"):
        state = update_lead_state(slot, int(user_id), stage=STAGE_GREETING, qualification={}, escalated=False)
        return {"status": "ok", "lead_state": state}

    return {"status": "ok", "lead_state": get_lead_state(slot, int(user_id))}
@router.get("/ai/smart-reply/leads/{slot}/{user_id}")
async def ai_smart_reply_lead_state(slot: str, user_id: int):
    if slot not in ACCOUNTS:
        return {"status": "error", "message": "Invalid slot"}
    from core.ai_smart_reply_store import get_lead_state

    return {"status": "ok", "lead_state": get_lead_state(slot, int(user_id))}
@router.post("/ai/smart-reply/assess")
async def ai_smart_reply_assess():
    """Run Karthik through the knowledge assessment battery and persist
    the resulting scorecard.

    Heavy-ish operation: it issues ~8 LLM calls. Run when the operator
    edits the business prompt or wants to re-verify Karthik. Returns
    the same scorecard payload that's persisted under
    config.last_assessment.
    """
    from core import ai_assessment
    from core.ai_smart_reply_store import get_config, save_assessment

    cfg = get_config()
    try:
        result = await ai_assessment.run_assessment(cfg)
    except Exception as e:
        return {"status": "error", "message": f"Assessment failed: {e}"}

    if result.get("status") == "ok":
        save_assessment(result)
    return result
@router.get("/ai/smart-reply/assessment")
async def ai_smart_reply_get_assessment():
    """Return the last persisted assessment scorecard plus the current
    gate state (`approved`/`override`/`blocked`) so the UI can render
    the right banner without doing the policy math itself."""
    from core.ai_smart_reply_store import get_config, is_assessment_approved

    cfg = get_config()
    last = cfg.get("last_assessment")
    return {
        "status":              "ok",
        "approved":            is_assessment_approved(),
        "require_assessment":  cfg.get("require_assessment", True),
        "manual_approval_at":  cfg.get("manual_approval_at"),
        "last_assessment":     last,
    }
@router.post("/ai/smart-reply/manual-approval")
async def ai_smart_reply_set_manual_approval(body: dict):
    """Operator override. `approved=true` lets AI suggestions run even
    when the last assessment was inconclusive. `approved=false` revokes
    the override and re-engages the gate."""
    from core.ai_smart_reply_store import is_assessment_approved, set_manual_approval

    approved = bool(body.get("approved"))
    cfg = set_manual_approval(approved=approved)
    return {
        "status":             "ok",
        "approved":           is_assessment_approved(),
        "manual_approval_at": cfg.get("manual_approval_at"),
    }
@router.post("/ai/knowledge/query")
async def knowledge_assistant_query(request: Request, body: dict):
    """Read-only, allowlisted natural-language queries over operational data."""
    question = str((body or {}).get("question") or "").strip()
    if not question:
        return {"status": "error", "message": "Question is required"}
    if len(question) > 500:
        return {"status": "error", "message": "Question is too long"}
    from core.dashboard_access import handler_reference_scope
    from core.knowledge_assistant import answer_question
    reference = handler_reference_scope(request, None)
    return await asyncio.to_thread(
        answer_question, question, reference=reference,
        session_id=str((body or {}).get("session_id") or "") or None,
    )
@router.delete("/ai/knowledge/session/{session_id}")
async def knowledge_assistant_session_end(session_id: str):
    from core.knowledge_assistant import end_session
    return {"status": "ok", "ended": end_session(session_id)}
@router.get("/ai/daily-briefing")
async def daily_ai_briefing_get(request: Request):
    """Return today's cached, authorized, strictly read-only briefing."""
    from core.daily_briefing import get_briefing

    payload = await asyncio.to_thread(get_briefing, reference=_viewer_reference(request))
    return {"status": "ok", "briefing": payload}
@router.post("/ai/daily-briefing/refresh")
async def daily_ai_briefing_refresh(request: Request):
    """Recalculate today's briefing without modifying operational records."""
    from core.daily_briefing import get_briefing

    payload = await asyncio.to_thread(
        get_briefing, reference=_viewer_reference(request), refresh=True,
    )
    return {"status": "ok", "message": "Briefing updated", "briefing": payload}


# ── Global OCR policy ────────────────────────────────────────────────────────
# One switch for every feature that may run Tesseract. Turning it off must turn
# OCR off project-wide, so this is the only place the value can be changed.

@router.get("/ai/ocr-policy")
async def read_ocr_policy(request: Request):
    """Current OCR mode. Readable by any signed-in operator."""
    from core.dashboard_access import operator_profile
    from core import ocr_policy

    operator_profile(request)  # rejects an unauthenticated caller
    return {"status": "ok", **ocr_policy.status()}


@router.put("/ai/ocr-policy")
async def update_ocr_policy(request: Request, body: dict):
    """Flip the switch. Admin only, and every change is audited."""
    from fastapi import HTTPException
    from core.dashboard_access import operator_profile
    from core import ocr_policy

    profile = operator_profile(request)
    if (profile.get("role") or "").strip().lower() != "admin":
        raise HTTPException(status_code=403, detail="Only an admin can change the OCR policy")

    raw = (body or {}).get("enabled")
    if not isinstance(raw, bool):
        raise HTTPException(status_code=400, detail="'enabled' must be true or false")

    actor = str(profile.get("username") or profile.get("name") or "admin")
    client = getattr(request, "client", None)
    result = ocr_policy.set_ocr_enabled(
        raw, actor=actor, source_ip=getattr(client, "host", "") or ""
    )
    return {"status": "ok", **result}


@router.get("/ai/ocr-policy/audit")
async def read_ocr_policy_audit(request: Request, limit: int = 20):
    """Who changed the switch, when, and from what to what. Admin only."""
    from fastapi import HTTPException
    from core.dashboard_access import operator_profile
    from core import ocr_policy

    if (operator_profile(request).get("role") or "").strip().lower() != "admin":
        raise HTTPException(status_code=403, detail="Only an admin can read the OCR policy audit")
    return {"status": "ok", "entries": ocr_policy.audit_log(limit)}
