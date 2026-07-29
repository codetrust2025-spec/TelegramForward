"""Auto-extracted auth routes (pure move from server.py)."""
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
    _duplicate_phone_login_response,
    _get_login_pending,
    _prepare_login_slot,
    _push_state,
    _slot_valid,
    _sync_login_state_slots,
    login_state,
    registry,
)

router = APIRouter()

@router.post("/login/send-otp")
async def send_otp(payload: dict):
    phone = payload.get("phone", "").strip()
    slot = payload.get("slot", "account1")
    if not phone:
        return {"success": False, "error": "Phone number required"}
    _sync_login_state_slots()
    if not _slot_valid(slot):
        return {
            "success": False,
            "error": f"Unknown account slot “{slot}”. Refresh the page, or add the slot again from Accounts.",
        }
    dup = _duplicate_phone_login_response(phone, slot)
    if dup:
        return dup
    try:
        await asyncio.wait_for(_prepare_login_slot(slot), timeout=45.0)

        async def _send_code():
            c = await telegram_client.get_login_client(slot)
            return await c.send_code_request(phone)

        result = await asyncio.wait_for(
            telegram_client.run_login_with_retry(slot, _send_code),
            timeout=55.0,
        )
        client = await telegram_client.get_login_client(slot)
        session_string = ""
        try:
            session_string = client.session.save() or ""
        except Exception:
            pass
        if session_string:
            telegram_client.remember_login_session_string(slot, session_string)
        pending = {
            "phone": phone,
            "phone_code_hash": result.phone_code_hash,
        }
        login_state[slot] = pending
        save_pending(
            slot,
            phone,
            result.phone_code_hash,
            session_string=session_string or None,
        )
        return {"success": True}
    except asyncio.TimeoutError:
        clear_pending(slot)
        await telegram_client.finalize_login_exclusive(slot)
        return {
            "success": False,
            "error": "Telegram login timed out. Wait 10 seconds, then tap Send OTP again.",
        }
    except Exception as e:
        clear_pending(slot)
        await telegram_client.finalize_login_exclusive(slot)
        err = str(e)
        if "database is locked" in err.lower():
            err = "Session file was busy. Wait 10 seconds, then tap Send OTP again."
        elif "flood" in err.lower() or "wait" in err.lower() and "seconds" in err.lower():
            err = f"Telegram rate limit: {err}. Try again later or use a different number."
        return {"success": False, "error": err}
@router.post("/login/verify-otp")
async def verify_otp(payload: dict):
    code = payload.get("code", "").strip()
    slot = (payload.get("slot") or "").strip()
    _sync_login_state_slots()
    if not _slot_valid(slot):
        return {"success": False, "error": "Invalid account slot — refresh the page and try again"}

    ls = _get_login_pending(slot)
    if not ls:
        return {
            "success": False,
            "error": (
                "Login session expired (server reloaded). "
                "Tap ← Back, send OTP again, then verify within a few minutes."
            ),
        }

    phone = ls.get("phone")
    phone_code_hash = ls.get("phone_code_hash")
    if not all([code, phone, phone_code_hash]):
        return {"success": False, "error": "Missing login state — send OTP again"}
    dup = _duplicate_phone_login_response(phone, slot)
    if dup:
        return dup
    try:
        async def _sign_in() -> None:
            client = await telegram_client.get_login_client(slot)
            await client.sign_in(phone, code, phone_code_hash=phone_code_hash)

        await telegram_client.run_login_with_retry(slot, _sign_in)

        client = await telegram_client.get_login_client(slot)
        if not await client.is_user_authorized():
            clear_pending(slot)
            await telegram_client.finalize_login_exclusive(slot)
            return {"success": False, "error": "Sign-in failed — send OTP again"}

        async def _get_me():
            c = await telegram_client.get_login_client(slot)
            return await c.get_me()

        me = await telegram_client.run_login_with_retry(slot, _get_me)
        me_phone = str(getattr(me, "phone", None) or phone or "")
        dup_me = _duplicate_phone_login_response(me_phone, slot)
        if dup_me:
            clear_pending(slot)
            await telegram_client.finalize_login_exclusive(slot)
            return dup_me
        await telegram_client.commit_login_session(slot)
        from core.account_info_store import build_info_from_me

        from core.subscription_accounts import enrich_account_info

        info = enrich_account_info(slot, build_info_from_me(me))
        login_state[slot] = {"phone": None, "phone_code_hash": None}
        clear_pending(slot)

        worker_started = await registry.complete_login(slot, info)

        workspace_mode = str(payload.get("workspace_mode") or "").strip().lower()
        if workspace_mode in ("forwarding", "forward"):
            from core.posting_mode import set_posting_mode

            set_posting_mode(
                slot,
                "forwarding",
                forward_dispatch="auto",
                campaign_enabled=False,
                forwarding_enabled=True,
            )
            w = registry.get_worker(slot)
            w._sync_posting_mode_ui()
        elif workspace_mode in ("campaign",):
            from core.posting_mode import set_posting_mode

            set_posting_mode(
                slot,
                "campaign",
                campaign_enabled=True,
                forwarding_enabled=False,
            )
            w = registry.get_worker(slot)
            w._sync_posting_mode_ui()

        await _push_state()

        async def _scan_joined_background() -> None:
            try:
                await registry.refresh_joined_counts(slot)
                await _push_state()
            except Exception:
                pass

        asyncio.create_task(_scan_joined_background())

        return {
            "success": True,
            "name": info["name"],
            "phone": info["phone"],
            "slot": slot,
            "worker_started": worker_started,
        }
    except Exception as e:
        await telegram_client.finalize_login_exclusive(slot)
        err = str(e)
        if "database is locked" in err.lower():
            err = (
                "Telegram session file is busy (another account task was using it). "
                "Wait 10 seconds, tap ← Back, send OTP again, then verify."
            )
        return {"success": False, "error": err}
@router.post("/login/logout")
async def logout(payload: dict = {}):
    slot = (payload.get("slot") or registry.active_account or "").strip()
    if slot not in ACCOUNTS:
        return {"success": False, "error": "Invalid slot"}
    login_state.setdefault(slot, {"phone": None, "phone_code_hash": None})
    try:
        await registry.logout_account(slot)
        login_state[slot] = {"phone": None, "phone_code_hash": None}
        await _push_state()
        return {"success": True, "slot": slot}
    except Exception as e:
        try:
            await registry.logout_account(slot)
            login_state[slot] = {"phone": None, "phone_code_hash": None}
            await _push_state()
        except Exception:
            pass
        return {"success": False, "error": str(e)}
@router.get("/login/status")
async def login_status():
    slot = registry.active_account
    if slot:
        info = registry.get_worker(slot).state.account_info
        if info:
            return {
                "logged_in": True,
                "name": info["name"],
                "username": info.get("username", ""),
                "phone": info["phone"],
                "slot": slot,
            }
    return {"logged_in": False}
