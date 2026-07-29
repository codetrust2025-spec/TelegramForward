"""Auto-extracted crm routes (pure move from server.py)."""
import asyncio
import json
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
    _crm_schedule_call_impl,
)

router = APIRouter()

@router.get("/crm/state")
async def crm_state():
    from services import crm_service

    crm_service.sync_leads_from_inbox()
    return {"status": "ok", **crm_service.build_crm_payload()}
@router.get("/crm/leads/{slot}/{user_id}")
async def crm_get_lead(slot: str, user_id: int):
    if slot not in ACCOUNTS:
        return {"status": "error", "message": "Invalid slot"}
    from services import crm_service

    lead = crm_service.get_lead_detail(slot, user_id)
    if not lead:
        return {"status": "error", "message": "Lead not found"}
    return {"status": "ok", "lead": lead}
@router.patch("/crm/leads/{slot}/{user_id}")
async def crm_patch_lead(slot: str, user_id: int, body: dict):
    if slot not in ACCOUNTS:
        return {"status": "error", "message": "Invalid slot"}
    from services import crm_service

    kwargs = {}
    if "status" in body:
        kwargs["status"] = body.get("status")
    if "notes" in body:
        kwargs["notes"] = body.get("notes")
    if "reminder_timestamp" in body:
        kwargs["reminder_timestamp"] = body.get("reminder_timestamp")
        kwargs["_has_reminder"] = True
    if body.get("mark_handled"):
        kwargs["mark_handled"] = True
    lead = await crm_service.update_lead(slot, int(user_id), **kwargs)
    return {"status": "ok", "lead": lead, "crm": crm_service.build_crm_payload()}
@router.post("/crm/leads/{slot}/{user_id}/link-phone")
async def crm_link_phone(slot: str, user_id: int, body: dict):
    if slot not in ACCOUNTS:
        return {"status": "error", "message": "Invalid slot"}
    phone = body.get("phone") or body.get("phone_e164") or ""
    from core.contact_link_store import link_phone
    from core.dm_store import load_inbox, save_inbox
    from services.crm_service import enrich_conversation

    link = link_phone(slot, int(user_id), str(phone), linked_by="manual")
    if not link:
        return {"status": "error", "message": "Invalid phone number"}

    data = load_inbox(slot)
    key = str(int(user_id))
    conv = (data.get("conversations") or {}).get(key)
    if conv:
        conv["phone_e164"] = link["phone_e164"]
        channels = set(conv.get("channels") or [])
        channels.update({"telegram", "whatsapp"})
        conv["channels"] = sorted(channels)
        data["conversations"][key] = conv
        save_inbox(slot, data)
        summary = enrich_conversation(
            slot,
            {
                "user_id": int(user_id),
                "username": conv.get("username") or "",
                "name": conv.get("name") or "",
                "last_message": conv.get("last_message") or "",
                "last_message_at": conv.get("last_message_at"),
                "unread_count": conv.get("unread_count") or 0,
                "phone_e164": link["phone_e164"],
                "channels": conv.get("channels"),
            },
        )
    else:
        summary = enrich_conversation(
            slot,
            {
                "user_id": int(user_id),
                "phone_e164": link["phone_e164"],
                "channels": ["telegram", "whatsapp"],
            },
        )

    return {"status": "ok", "link": link, "conversation": summary}
@router.post("/crm/leads/{slot}/{user_id}/mark-handled")
async def crm_mark_handled(slot: str, user_id: int):
    if slot not in ACCOUNTS:
        return {"status": "error", "message": "Invalid slot"}
    from services import crm_service

    try:
        lead = await crm_service.mark_reply_handled(slot, int(user_id))
        return {"status": "ok", "lead": lead, "crm": crm_service.build_crm_payload()}
    except ValueError as e:
        return {"status": "error", "message": str(e)}
@router.post("/crm/leads/{slot}/{user_id}/follow-up")
async def crm_follow_up(slot: str, user_id: int, body: dict):
    if slot not in ACCOUNTS:
        return {"status": "error", "message": "Invalid slot"}
    from services import crm_service

    hours = body.get("hours")
    if hours is None and body.get("preset") == "tomorrow":
        hours = 24.0
    elif hours is None:
        hours = 2.0
    lead = await crm_service.set_follow_up(slot, int(user_id), hours=float(hours))
    return {"status": "ok", "lead": lead, "crm": crm_service.build_crm_payload()}
@router.get("/crm/call-now/options")
async def crm_call_now_options(
    account_id: str = Query(..., alias="account_id"),
    user_id: int = Query(...),
):
    if account_id not in ACCOUNTS:
        return {"status": "error", "message": "Invalid account_id"}
    from services import call_service

    contact = call_service.resolve_contact(account_id, int(user_id))
    return {
        "status": "ok",
        "contact": contact,
        "options": call_service.build_live_call_options(contact),
    }
@router.post("/crm/call-now")
async def crm_call_now(body: dict):
    slot = body.get("account_id") or body.get("slot")
    user_id = body.get("user_id")
    if not slot or slot not in ACCOUNTS:
        return {"status": "error", "message": "Invalid account_id"}
    if user_id is None:
        return {"status": "error", "message": "user_id required"}
    call_type = body.get("call_type") or "telegram"
    send_message = body.get("send_message", True)
    from services import call_service, crm_service as _crm

    try:
        result = await call_service.initiate_live_call(
            slot,
            int(user_id),
            call_type=str(call_type),
            send_message=bool(send_message),
        )
        lead = _crm.get_lead_detail(slot, int(user_id))
        return {
            "status": "ok",
            **result,
            "lead": lead,
            "crm": _crm.build_crm_payload(),
        }
    except ValueError as e:
        return {"status": "error", "message": str(e)}
    except Exception as e:
        return {"status": "error", "message": str(e)}
@router.post("/crm/karthik/block-spam-chats")
async def crm_karthik_block_spam_chats(body: dict | None = None):
    """Karthik spam guard: scan inbox threads and block solicitation/scam chats."""
    body = body or {}
    slot = body.get("account_id") or body.get("slot")
    from services import crm_service
    from services.spam_guard_service import scan_inbox_and_block_spam

    if slot is not None and slot not in ACCOUNTS:
        return {"status": "error", "message": "Invalid slot"}
    result = await scan_inbox_and_block_spam(slot=slot)
    return {"status": "ok", "crm": crm_service.build_crm_payload(), **result}
@router.post("/crm/unblock")
async def crm_unblock(body: dict):
    slot = body.get("account_id") or body.get("slot")
    user_id = body.get("user_id")
    if not slot or slot not in ACCOUNTS:
        return {"status": "error", "message": "Invalid account_id"}
    if user_id is None:
        return {"status": "error", "message": "user_id required"}
    from services import block_service, crm_service as _crm

    try:
        result = await block_service.unblock_lead(slot, int(user_id))
        lead = result["lead"]
        await _crm.broadcast_crm_update(slot, int(user_id), lead)
        return {"status": "ok", "lead": lead, "crm": _crm.build_crm_payload()}
    except Exception as e:
        return {"status": "error", "message": str(e)}
@router.post("/crm/schedule-call")
async def crm_schedule_call_body(body: dict):
    """Schedule a call (flat payload: account_id, user_id, scheduled_time, call_type, notes)."""
    slot = body.get("account_id") or body.get("slot")
    user_id = body.get("user_id")
    if not slot or slot not in ACCOUNTS:
        return {"status": "error", "message": "Invalid account_id"}
    if user_id is None:
        return {"status": "error", "message": "user_id required"}
    return await _crm_schedule_call_impl(slot, int(user_id), body)
@router.post("/crm/leads/{slot}/{user_id}/calls")
async def crm_schedule_call(slot: str, user_id: int, body: dict):
    if slot not in ACCOUNTS:
        return {"status": "error", "message": "Invalid slot"}
    return await _crm_schedule_call_impl(slot, int(user_id), body)
@router.post("/crm/leads/{slot}/{user_id}/calls/complete")
async def crm_complete_call(slot: str, user_id: int, body: dict):
    if slot not in ACCOUNTS:
        return {"status": "error", "message": "Invalid slot"}
    from services import call_service, crm_service

    outcome = body.get("outcome_status") or body.get("status")
    call = await call_service.complete_lead_call(
        slot, int(user_id), outcome_status=outcome
    )
    lead = crm_service.get_lead_detail(slot, int(user_id))
    return {"status": "ok", "call": call, "lead": lead, "crm": crm_service.build_crm_payload()}
