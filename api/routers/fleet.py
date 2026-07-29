"""Auto-extracted fleet routes (pure move from server.py)."""
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
    _push_state,
    _require_fleet_admin,
    _start_all_background,
    _start_all_task,
    registry,
)

router = APIRouter()

@router.post("/start", dependencies=[Depends(_require_fleet_admin)])
async def start_all():
    """Queue start for every logged-in account; return immediately for UI responsiveness."""
    global _start_all_task
    if _start_all_task is not None and not _start_all_task.done():
        return {"status": "queued", "accounts": [], "message": "Start all already in progress"}
    if not any(registry.get_runtime(slot).has_login() for slot in ACCOUNTS):
        return {"status": "error", "accounts": [], "message": "No logged-in accounts"}
    _start_all_task = asyncio.create_task(_start_all_background(one_shot=False))
    return {"status": "queued", "accounts": [], "message": "Starting logged-in accounts in background"}
@router.post("/start-test", dependencies=[Depends(_require_fleet_admin)])
async def start_test_all():
    global _start_all_task
    if _start_all_task is not None and not _start_all_task.done():
        return {"status": "queued", "accounts": [], "message": "Start all already in progress"}
    if not any(registry.get_runtime(slot).has_login() for slot in ACCOUNTS):
        return {"status": "error", "accounts": [], "message": "No logged-in accounts"}
    _start_all_task = asyncio.create_task(_start_all_background(one_shot=True))
    return {"status": "queued", "accounts": [], "message": "Starting one test cycle in background"}
@router.post("/stop", dependencies=[Depends(_require_fleet_admin)])
async def stop_all():
    registry.stop_all()
    await _push_state()
    return {"status": "stopped", **registry.build_ui_state()}
@router.get("/fleet/defaults")
async def fleet_defaults_get():
    from core.fleet_defaults import get_fleet_defaults

    return {"status": "ok", **get_fleet_defaults()}
@router.post("/fleet/defaults")
async def fleet_defaults_post(body: dict | None = None):
    from core.fleet_defaults import get_fleet_defaults, save_fleet_defaults

    payload = body or {}
    saved = save_fleet_defaults(
        forward_source_url=payload.get("forward_source_url"),
        campaign_message=payload.get("campaign_message"),
    )
    if payload.get("campaign_message"):
        from core.message_store import save_message

        save_message(str(payload.get("campaign_message") or "").strip())
    await _push_state()
    return {"status": "ok", **saved}
@router.post("/fleet/apply-forwarding")
async def fleet_apply_forwarding(body: dict | None = None):
    """Enable forwarding + optional t.me link on all logged-in accounts (skips running)."""
    from services.fleet_setup_service import apply_forwarding_bulk

    payload = body or {}
    result = apply_forwarding_bulk(
        registry=registry,
        source_url=payload.get("source_url"),
        use_saved_default=bool(payload.get("use_saved_default")),
        forward_dispatch=str(payload.get("forward_dispatch") or "auto"),
    )
    await _push_state()
    return {"status": "ok", **result, **registry.build_ui_state()}
@router.post("/fleet/apply-campaign")
async def fleet_apply_campaign(body: dict | None = None):
    """Enable campaign + optional message on all logged-in accounts (skips running)."""
    from services.fleet_setup_service import apply_campaign_bulk

    payload = body or {}
    result = apply_campaign_bulk(
        registry=registry,
        message=payload.get("message"),
        use_saved_default=bool(payload.get("use_saved_default")),
    )
    await _push_state()
    return {"status": "ok", **result, **registry.build_ui_state()}
@router.post("/fleet/apply-source-url")
async def fleet_apply_source_url(body: dict | None = None):
    """Apply t.me post link to logged-in accounts without changing mode (skips running)."""
    from services.fleet_setup_service import apply_forward_source_only

    payload = body or {}
    result = apply_forward_source_only(
        registry=registry,
        source_url=payload.get("source_url"),
        use_saved_default=bool(payload.get("use_saved_default")),
    )
    await _push_state()
    return {"status": "ok", **result}
