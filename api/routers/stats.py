"""Auto-extracted stats routes (pure move from server.py)."""
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
    _perform_stats_reset,
    _require_fleet_admin,
    registry,
)

router = APIRouter()

@router.get("/metrics")
async def fleet_metrics():
    from core.fleet_rate_coordinator import fleet_rate_coordinator
    from core.observability.account_metrics import metrics_store

    return {
        "status": "ok",
        "metrics": metrics_store.all_snapshots(),
        "fleet_rate": fleet_rate_coordinator.snapshot(),
    }
@router.get("/metrics/{slot}")
async def account_metrics(slot: str):
    if slot not in ACCOUNTS:
        return {"status": "error", "message": "Invalid slot"}
    from core.observability.account_metrics import metrics_store

    return {"status": "ok", "metrics": metrics_store.snapshot(slot)}
@router.get("/stats/daily")
async def get_daily_stats():
    from core.daily_stats import refresh_daily_stats

    daily_stats, auto_reset = await asyncio.to_thread(
        refresh_daily_stats, list(ACCOUNTS)
    )
    if auto_reset:
        if auto_reset.scope == "global":
            registry.reset_stats_display_counters(None)
        else:
            for slot in auto_reset.account_ids:
                registry.reset_stats_display_counters(slot)
    return {"status": "ok", "daily_stats": daily_stats}
@router.post("/stats/reset", dependencies=[Depends(_require_fleet_admin)])
async def reset_stats(payload: dict | None = None):
    """Reset daily stat counters and live tick display from now. Chats/logs are kept."""
    return await _perform_stats_reset(payload or {})
@router.post("/stats/reset-24h")
async def reset_daily_stats_24h():
    """Alias for global stats reset (backward compatible)."""
    return await _perform_stats_reset({})
