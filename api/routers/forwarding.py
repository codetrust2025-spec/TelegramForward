"""Auto-extracted forwarding routes (pure move from server.py)."""
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

router = APIRouter()

@router.get("/forward-message/settings")
async def forward_message_settings_get():
    from services.forward_message_service import forward_message_service

    return {"status": "ok", "settings": forward_message_service.get_settings()}
@router.post("/forward-message/settings")
async def forward_message_settings_post(body: dict):
    from services.forward_message_service import forward_message_service

    try:
        settings = forward_message_service.save_settings(body or {})
        return {"status": "ok", "settings": settings}
    except ValueError as e:
        return {"status": "error", "message": str(e)}
