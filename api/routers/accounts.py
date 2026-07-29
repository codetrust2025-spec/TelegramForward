"""Auto-extracted accounts routes (pure move from server.py)."""
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
    CODE_VERSION,
    _push_state,
    _require_fleet_admin,
    _sync_login_state_slots,
    _worker_running,
    login_state,
    registry,
)

router = APIRouter()

@router.post("/account/{slot}/start", dependencies=[Depends(_require_fleet_admin)])
async def start_account(
    slot: str,
    one_shot: bool = Query(False),
    feature: str = Query(""),
):
    if slot not in ACCOUNTS:
        return {"status": "error", "message": "Invalid slot"}
    campaign = forwarding = None
    feat = (feature or "").strip().lower()
    if feat == "campaign":
        campaign = True
    elif feat == "forwarding":
        forwarding = True
    elif feat and feat not in ("all", "both"):
        return {"status": "error", "message": "feature must be campaign, forwarding, or empty"}
    from core.account_shutdown import is_shutdown_active, shutdown_info_for_ui

    if is_shutdown_active(slot):
        info = shutdown_info_for_ui(slot) or {}
        return {
            "status": "error",
            "message": "Account is on shutdown list (no posts for 6+ hours). Clear shutdown to start.",
            "shutdown": info,
        }
    if not await registry.start_account(
        slot,
        one_shot=one_shot,
        campaign=campaign,
        forwarding=forwarding,
    ):
        w = registry.get_worker(slot)
        if not w.state.account_info:
            return {"status": "error", "message": f"{slot} not logged in"}
        if not (w.state.campaign_running or w.state.forwarding_running):
            from core.posting_mode import load_posting_mode

            cfg = load_posting_mode(slot)
            if not cfg.campaign_enabled and not cfg.forwarding_enabled:
                return {"status": "error", "message": "Enable campaign or forwarding first"}
        return {"status": "already_running"}
    await _push_state()
    return {"status": "started", "slot": slot, "feature": feat or "all"}
@router.post("/account/{slot}/shutdown", dependencies=[Depends(_require_fleet_admin)])
async def put_account_shutdown(slot: str):
    """Manually move an account to the shutdown (rest) list and stop it."""
    if slot not in ACCOUNTS:
        return {"status": "error", "message": "Invalid slot"}
    from core.account_shutdown import put_on_shutdown_list
    from core.worker_persistence import mark_stopped

    w = registry.get_worker(slot)
    if not w.state.account_info:
        return {"status": "error", "message": f"{slot} not logged in"}
    was_running = bool(w.state.running)
    put_on_shutdown_list(slot, reason="manual", was_running=was_running)
    try:
        await registry.stop_account(slot)
    except Exception:
        pass
    mark_stopped(slot)
    await _push_state()
    return {"status": "ok", "slot": slot, **registry.build_ui_state()}
@router.post("/account/{slot}/shutdown/clear", dependencies=[Depends(_require_fleet_admin)])
async def clear_account_shutdown(slot: str):
    if slot not in ACCOUNTS:
        return {"status": "error", "message": "Invalid slot"}
    from core.account_shutdown import clear_shutdown

    if not clear_shutdown(slot):
        return {"status": "not_found", "slot": slot}
    await _push_state()
    return {"status": "ok", "slot": slot, **registry.build_ui_state()}
@router.post("/account/shutdown/clear-all", dependencies=[Depends(_require_fleet_admin)])
@router.post("/shutdown/clear-all", dependencies=[Depends(_require_fleet_admin)])
async def clear_all_shutdowns_route(body: dict | None = None):
    """Return all accounts to Campaign/Forwarding tabs; optional stats reset for shutdown test cycle."""
    from core.account_shutdown import clear_all_shutdowns

    payload = body or {}
    cleared = clear_all_shutdowns()
    if payload.get("reset_stats") and cleared:
        from core.join_cycle import daily_join_count_for_reset
        from core.send_stats import invalidate_cache
        from core.stats_reset import StatsResetDebounced, set_reset_timestamp

        for slot in cleared:
            if slot not in ACCOUNTS:
                continue
            try:
                set_reset_timestamp(
                    account_id=slot,
                    join_baselines={slot: daily_join_count_for_reset(slot)},
                )
            except StatsResetDebounced:
                pass
            invalidate_cache(slot)
    await _push_state()
    return {
        "status": "ok",
        "cleared": cleared,
        "cleared_count": len(cleared),
        "reset_stats": bool(payload.get("reset_stats")),
        **registry.build_ui_state(),
    }
@router.post("/account/{slot}/stop", dependencies=[Depends(_require_fleet_admin)])
async def stop_account(slot: str, feature: str = Query("")):
    if slot not in ACCOUNTS:
        return {"status": "error", "message": "Invalid slot"}
    feat = (feature or "").strip().lower()
    campaign = forwarding = None
    if feat == "campaign":
        campaign = False
    elif feat == "forwarding":
        forwarding = False
    elif feat and feat not in ("all", "both"):
        return {"status": "error", "message": "feature must be campaign, forwarding, or empty"}
    await registry.stop_account(slot, campaign=campaign, forwarding=forwarding)
    await _push_state()
    return {"status": "stopped", "slot": slot, "feature": feat or "all", **registry.build_ui_state()}
@router.post("/account/{slot}/display-name")
async def set_account_display_name(slot: str, body: dict):
    """Set dashboard profile label for one account (does not change Telegram)."""
    if slot not in ACCOUNTS:
        return {"success": False, "error": "Invalid slot"}
    payload = body or {}
    display_name = str(payload.get("display_name") or "").strip()
    if not display_name:
        return {"success": False, "error": "Display name cannot be empty"}
    if len(display_name) > 48:
        return {"success": False, "error": "Display name too long (max 48 characters)"}

    info = load_account_info(slot)
    if not info or not info.get("phone"):
        return {"success": False, "error": "Account not logged in"}

    save_account_info(slot, {**info, "display_name": display_name})
    w = registry.get_worker(slot)
    refreshed = load_account_info(slot)
    if refreshed:
        w.state.account_info = refreshed
    await _push_state()
    return {"success": True, "account_info": w.state.account_info}
@router.get("/account/{slot}/posting-mode")
async def get_posting_mode(slot: str):
    if slot not in ACCOUNTS:
        return {"status": "error", "message": "Invalid slot"}
    from core.posting_mode import load_posting_mode

    return {"status": "ok", **load_posting_mode(slot).to_dict(slot)}
@router.post("/account/{slot}/posting-mode")
async def set_posting_mode_endpoint(slot: str, body: dict):
    if slot not in ACCOUNTS:
        return {"status": "error", "message": "Invalid slot"}
    from core.posting_mode import set_posting_mode

    payload = body or {}
    mode = str(payload.get("mode") or "").strip()
    forward_source_type = payload.get("forward_source_type")
    if forward_source_type is None:
        forward_source_type = payload.get("source_type")
    forward_dispatch = payload.get("forward_dispatch")
    campaign_enabled = payload.get("campaign_enabled")
    forwarding_enabled = payload.get("forwarding_enabled")
    if (
        not mode
        and forward_source_type is None
        and forward_dispatch is None
        and campaign_enabled is None
        and forwarding_enabled is None
    ):
        return {
            "status": "error",
            "message": "mode, campaign_enabled, forwarding_enabled, forward_source_type, or forward_dispatch required",
        }
    try:
        cfg = set_posting_mode(
            slot,
            mode,
            forward_source_type=forward_source_type,
            forward_dispatch=forward_dispatch,
            campaign_enabled=campaign_enabled,
            forwarding_enabled=forwarding_enabled,
        )
    except ValueError as e:
        return {"status": "error", "message": str(e)}
    w = registry.get_worker(slot)
    w._sync_posting_mode_ui()
    await _push_state()
    return {"status": "ok", **cfg.to_dict(slot)}
@router.post("/account/{slot}/forwarding/source")
async def set_forwarding_source_endpoint(slot: str, body: dict):
    if slot not in ACCOUNTS:
        return {"status": "error", "message": "Invalid slot"}
    from core.posting_mode import set_forwarding_source

    w = registry.get_worker(slot)
    if w.state.running:
        return {
            "status": "error",
            "message": "Stop the worker before changing forward source",
        }
    payload = body or {}
    try:
        cfg = set_forwarding_source(
            slot,
            source_url=payload.get("source_url"),
            source_peer=payload.get("source_peer"),
            source_message_id=payload.get("source_message_id"),
        )
    except ValueError as e:
        return {"status": "error", "message": str(e)}
    w._sync_posting_mode_ui()
    await _push_state()
    return {"status": "ok", **cfg.to_dict(slot)}
@router.get("/account/{slot}/forward-message/groups")
async def forward_message_groups(slot: str, force_refresh: bool = False):
    if slot not in ACCOUNTS:
        return {"status": "error", "message": "Invalid slot"}
    from services.forward_message_service import forward_message_service

    try:
        payload = await forward_message_service.list_joined_groups(
            slot, force_refresh=bool(force_refresh)
        )
        return {"status": "ok", **payload}
    except Exception as e:
        return {"status": "error", "message": str(e)}
@router.post("/account/{slot}/forward-message/preview")
async def forward_message_preview(slot: str, body: dict):
    if slot not in ACCOUNTS:
        return {"status": "error", "message": "Invalid slot"}
    from services.forward_message_service import forward_message_service

    payload = body or {}
    try:
        job = await forward_message_service.resolve_source(
            slot,
            source_url=str(payload.get("source_url") or "").strip(),
            source_peer=str(payload.get("source_peer") or "").strip(),
            source_message_id=int(payload.get("source_message_id") or 0),
            worker_running=_worker_running(slot),
        )
        return {"status": "ok", "job": job}
    except ValueError as e:
        return {"status": "error", "message": str(e)}
    except Exception as e:
        return {"status": "error", "message": str(e)}
@router.get("/account/{slot}/forward-message/job")
async def forward_message_job_status(slot: str):
    if slot not in ACCOUNTS:
        return {"status": "error", "message": "Invalid slot"}
    from services.forward_message_service import forward_message_service

    return {"status": "ok", "job": forward_message_service.job_dict(slot)}
@router.post("/account/{slot}/forward-message/start", dependencies=[Depends(_require_fleet_admin)])
async def forward_message_start(slot: str, body: dict):
    if slot not in ACCOUNTS:
        return {"status": "error", "message": "Invalid slot"}
    from services.forward_message_service import forward_message_service

    payload = body or {}
    target_ids = payload.get("target_ids") or payload.get("targets") or []
    try:
        batch_size = payload.get("batch_size")
        job = await forward_message_service.start_job(
            slot,
            source_url=str(payload.get("source_url") or "").strip(),
            source_peer=str(payload.get("source_peer") or "").strip(),
            source_message_id=int(payload.get("source_message_id") or 0),
            target_ids=target_ids,
            batch_size=int(batch_size) if batch_size is not None else None,
            worker_running=_worker_running(slot),
            use_posting_mode_source=bool(payload.get("use_posting_mode_source", True)),
            human_pace=bool(payload.get("human_pace", True)),
        )
        await _push_state()
        return {"status": "ok", "job": job}
    except ValueError as e:
        return {"status": "error", "message": str(e)}
    except Exception as e:
        return {"status": "error", "message": str(e)}
@router.get("/account/{slot}/forward-cycle/selection")
async def forward_cycle_selection_get(slot: str):
    if slot not in ACCOUNTS:
        return {"status": "error", "message": "Invalid slot"}
    from core.posting_mode import load_posting_mode

    cfg = load_posting_mode(slot)
    return {
        "status": "ok",
        "target_ids": list(cfg.forwarding.forward_selected_target_ids or []),
        "forward_dispatch": cfg.forwarding.forward_dispatch,
    }
@router.get("/account/{slot}/forward-intelligence")
async def forward_intelligence_stats(slot: str):
    """Get forwarding intelligence statistics and adaptive timing info"""
    if slot not in ACCOUNTS:
        return {"status": "error", "message": "Invalid slot"}
    
    try:
        from core.forward_intelligence import load_forward_intelligence
        
        intel = load_forward_intelligence(slot)
        stats = intel.get_stats()
        
        # Add next tick prediction
        health_score = ACCOUNTS[slot].get("health_score", 100.0)
        next_interval = intel.compute_next_tick_interval(health_score)
        should_skip, skip_reason = intel.should_skip_tick(health_score)
        
        return {
            "status": "ok",
            "intelligence": {
                "stats": stats,
                "next_tick_interval_seconds": next_interval,
                "next_tick_interval_minutes": round(next_interval / 60, 1),
                "should_skip_next": should_skip,
                "skip_reason": skip_reason if should_skip else None,
                "dead_peers_sample": list(intel.get_dead_peer_set())[:20],  # First 20
            }
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}
@router.post("/account/{slot}/forward-cycle/selection")
async def forward_cycle_selection_save(slot: str, body: dict):
    if slot not in ACCOUNTS:
        return {"status": "error", "message": "Invalid slot"}
    from core.posting_mode import save_forward_selection

    ids = (body or {}).get("target_ids") or (body or {}).get("targets") or []
    cfg = save_forward_selection(slot, ids)
    await _push_state()
    return {
        "status": "ok",
        "target_ids": list(cfg.forwarding.forward_selected_target_ids or []),
    }
@router.post("/account/{slot}/forward-message/cancel")
async def forward_message_cancel(slot: str):
    if slot not in ACCOUNTS:
        return {"status": "error", "message": "Invalid slot"}
    from services.forward_message_service import forward_message_service

    job = await forward_message_service.cancel_job(slot)
    await _push_state()
    return {"status": "ok", "job": job}
@router.post("/account/{slot}/restart")
async def restart_account(slot: str):
    if slot not in ACCOUNTS:
        return {"status": "error", "message": "Invalid slot"}
    ok = await manager.restart_account(slot)
    await _push_state()
    return {"status": "restarted" if ok else "error", "slot": slot, **registry.build_ui_state()}
@router.post("/account/{slot}/clear-logs")
async def clear_account_logs(slot: str):
    if slot not in ACCOUNTS:
        return {"status": "error", "message": "Invalid slot"}
    await registry.clear_logs(slot)
    await _push_state()
    return {"status": "cleared", "slot": slot, **registry.build_ui_state()}
@router.get("/account/{slot}/status")
async def account_status(slot: str):
    if slot not in ACCOUNTS:
        return {"status": "error", "message": "Invalid slot"}
    return {"status": "ok", **manager.get_status(slot)}
@router.post("/accounts/restore-sessions")
async def restore_sessions():
    """
    Re-read Telethon .session files and rebuild account_info for every slot.
    No OTP needed when session files are valid. Safe to call after deploy/restart.
    """
    info = await registry.refresh_all_info()
    restored = [s for s, v in info.items() if v and v.get("phone")]
    await _push_state()
    return {
        "success": True,
        "restored": restored,
        "count": len(restored),
        "message": (
            f"Restored {len(restored)} account(s) from session files"
            if restored
            else "No valid sessions found — log in with OTP for each account"
        ),
    }
@router.get("/accounts")
async def list_accounts():
    """Account slots configured on this server (use for dashboard before WebSocket connects)."""
    from core.config import ACCOUNTS as _accounts, ACCOUNT_SLOTS as _slots
    from core.account_info_store import load_account_info
    from core.subscription_accounts import compute_subscription_slots, enrich_account_info

    info_map = {
        s: enrich_account_info(s, load_account_info(s))
        for s in _accounts
    }

    return {
        "account_slots": list(_slots),
        "subscription_slots": compute_subscription_slots(info_map),
        "count": len(_slots),
        "code_version": CODE_VERSION,
    }
@router.post("/accounts/provision-slot")
async def provision_account_slot():
    """Add account11+ when all existing slots are logged in."""
    from core.config import ACCOUNT_SLOTS, provision_next_account_slot, sync_accounts_bindings

    slot = provision_next_account_slot()
    sync_accounts_bindings()
    _sync_login_state_slots()
    registry.register_new_slot(slot)
    login_state.setdefault(slot, {"phone": None, "phone_code_hash": None})
    registry.active_account = slot
    await _push_state()
    return {
        "status": "ok",
        "slot": slot,
        "account_slots": list(ACCOUNT_SLOTS),
        "message": f"Added {slot} — log in with phone + OTP below.",
        **registry.build_ui_state(),
    }
@router.post("/account/switch")
async def switch_account(payload: dict):
    slot = payload.get("slot")
    if slot not in ACCOUNTS:
        return {"success": False, "error": "Invalid slot"}
    registry.active_account = slot
    await _push_state()
    return {"success": True, "active_account": slot}
@router.get("/account/status")
async def account_status():
    info = await registry.refresh_all_info()
    return {
        "active_account": registry.active_account,
        "account_info": info,
    }
@router.post("/account/refresh-joined")
async def refresh_joined_counts(payload: dict = {}):
    """Scan Telegram dialogs and store joined group/channel counts for one account."""
    slot = (payload.get("slot") or registry.active_account or "").strip()
    if slot not in ACCOUNTS:
        return {"success": False, "error": "Invalid slot"}
    w = registry.get_worker(slot)
    if not w.state.account_info and not load_account_info(slot):
        return {"success": False, "error": f"{slot} not logged in"}
    try:
        was_running = w.state.running
        base_info = w.state.account_info or load_account_info(slot) or {}

        async def _run_refresh() -> None:
            result = await registry.refresh_joined_counts(slot)
            if result:
                await _push_state()

        if was_running:
            asyncio.create_task(_run_refresh())
            info = base_info
        else:
            info = await registry.refresh_joined_counts(slot)
            if info:
                await _push_state()

        if not info:
            return {"success": False, "error": "Could not read joined counts"}
        has_counts = info.get("joined_total") is not None
        resp = {
            "success": True,
            "slot": slot,
            "joined_groups": info.get("joined_groups", 0),
            "joined_channels": info.get("joined_channels", 0),
            "joined_total": info.get("joined_total", 0),
            "joined_updated_at": info.get("joined_updated_at", ""),
        }
        if was_running:
            resp["queued"] = True
            resp["message"] = (
                "Background scan started — On Telegram count updates live via WebSocket"
            )
        elif not has_counts:
            resp["queued"] = True
            resp["message"] = "Scan in progress — count appears shortly"
        if info.get("joined_scan_partial"):
            resp["partial"] = True
            resp["partial_reason"] = info.get("joined_scan_partial_reason") or (
                "Group count may be incomplete — scan timed out; try again"
            )
        return resp
    except Exception as e:
        return {"success": False, "error": str(e)}
