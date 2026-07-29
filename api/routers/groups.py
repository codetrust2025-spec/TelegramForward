"""Auto-extracted groups routes (pure move from server.py)."""
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
    _parse_uploaded_groups,
    _push_state,
    registry,
)

router = APIRouter()

@router.get("/groups")
async def get_groups():
    groups = load_master_groups()
    return {"groups": groups, "total": len(groups)}
@router.get("/groups/removed")
async def get_removed_groups():
    invalid, blocked = set(), set()
    for slot in ACCOUNTS:
        inv, blk = load_account_dead(slot)
        invalid |= inv
        blocked |= blk
    return {"invalid": sorted(invalid), "blocked": sorted(blocked)}
@router.get("/groups/lists")
async def get_group_lists(slot: str | None = None):
    """
    Per-account dead (invalid/blocked) and good (active) group lists.
    cycle_success = groups that succeeded in the current/last worker cycle.
    """
    target = slot if slot in ACCOUNTS else registry.active_account
    if target not in ACCOUNTS:
        target = ACCOUNT_SLOTS[0]

    lists = build_group_lists(target)
    w = registry.get_worker(target)
    st = w.state
    cycle_success = list(st.success_list)
    cycle_failed = [
        {"group": x.get("group", ""), "reason": x.get("reason", "")}
        for x in st.failed_list
        if isinstance(x, dict)
    ]

    return {
        **lists,
        "cycle_success": cycle_success,
        "cycle_success_count": len(cycle_success),
        "cycle_failed": cycle_failed,
        "cycle_failed_count": len(cycle_failed),
    }
@router.get("/groups/health")
async def get_group_health(slot: str | None = None):
    """
    Live classification of one account's assigned groups into:
      healthy, cooling (recently_processed), risky (risky_until), blocked, invalid.
    Always reads fresh from disk (group_intelligence + dead lists + master).
    """
    from core.groups_store import build_group_health

    target = slot if slot in ACCOUNTS else registry.active_account
    if target not in ACCOUNTS:
        target = ACCOUNT_SLOTS[0]
    return build_group_health(target)
@router.get("/groups/total-list")
async def get_total_joined_list():
    """
    Aggregate the joined groups/channels from every logged-in account into a
    single deduped list. Each entry includes which accounts have it joined.

    Strategy: try a string-session scan first (no contention with the running
    worker). If that fails (no string session), fall back to a worker-session
    scan after the worker briefly releases the file lock.
    """
    from core.account_info_store import load_account_info
    from core.dm_string_session import run_with_string_session
    from core.group_assignment import active_slots
    from core.telegram_client import release_session, run_group_operation
    from features.telegram_joined_stats import fetch_joined_dialog_details

    actives = active_slots()
    aggregated: dict[int, dict] = {}
    per_account: dict[str, dict] = {}
    started_at = datetime.now()

    for slot in actives:
        info = load_account_info(slot) or {}
        account_label = (info.get("name") or info.get("username") or info.get("phone") or slot)
        per_account[slot] = {
            "label": account_label,
            "count": 0,
            "error": None,
            "elapsed_ms": 0,
        }
        slot_started = datetime.now()

        async def _op(client):
            return await fetch_joined_dialog_details(client)

        details: list[dict] | None = None
        try:
            scan = await asyncio.wait_for(
                run_with_string_session(slot, fetch_joined_dialog_details, attempts=2),
                timeout=200,
            )
            if isinstance(scan, dict):
                details = list(scan.get("targets") or [])
            elif isinstance(scan, list):
                details = scan
        except Exception as e_ss:
            try:
                await release_session(slot, wait=1.5)
                scan = await asyncio.wait_for(
                    run_group_operation(slot, _op, attempts=2),
                    timeout=200,
                )
                if isinstance(scan, dict):
                    details = list(scan.get("targets") or [])
                elif isinstance(scan, list):
                    details = scan
            except Exception as e_w:
                per_account[slot]["error"] = f"string:{type(e_ss).__name__}; worker:{type(e_w).__name__}: {e_w}"
            finally:
                try:
                    await release_session(slot, wait=0.3)
                except Exception:
                    pass

        per_account[slot]["elapsed_ms"] = int((datetime.now() - slot_started).total_seconds() * 1000)
        if not details:
            continue
        per_account[slot]["count"] = len(details)
        for d in details:
            ent_id = d.get("id")
            if not isinstance(ent_id, int):
                continue
            existing = aggregated.get(ent_id)
            if existing is None:
                aggregated[ent_id] = {
                    "id": ent_id,
                    "type": d.get("type") or "",
                    "name": d.get("name") or "",
                    "username": d.get("username") or "",
                    "link": d.get("link") or "",
                    "members": d.get("members"),
                    "accounts": [slot],
                }
            else:
                if slot not in existing["accounts"]:
                    existing["accounts"].append(slot)
                if not existing.get("name") and d.get("name"):
                    existing["name"] = d["name"]
                if not existing.get("username") and d.get("username"):
                    existing["username"] = d["username"]
                if not existing.get("link") and d.get("link"):
                    existing["link"] = d["link"]
                if existing.get("members") is None and isinstance(d.get("members"), int):
                    existing["members"] = d["members"]

    items = sorted(aggregated.values(), key=lambda x: (x.get("type") or "", (x.get("name") or "").lower()))
    groups_count = sum(1 for x in items if x.get("type") == "group")
    channels_count = sum(1 for x in items if x.get("type") == "channel")
    return {
        "generated_at": started_at.strftime("%Y-%m-%d %H:%M:%S"),
        "logged_in_accounts": actives,
        "per_account": per_account,
        "totals": {
            "unique": len(items),
            "groups": groups_count,
            "channels": channels_count,
        },
        "items": items,
    }
@router.get("/groups/health-summary")
async def get_group_health_summary():
    """Fleet-wide rollup of group health across all logged-in accounts."""
    from core.group_assignment import active_slots
    from core.groups_store import build_group_health

    totals = {"healthy": 0, "cooling": 0, "risky": 0, "blocked": 0, "invalid": 0, "assigned": 0}
    per_slot = []
    actives = active_slots()
    for slot in ACCOUNT_SLOTS:
        snap = build_group_health(slot)
        c = snap.get("counts", {})
        for k in totals:
            totals[k] += int(c.get(k, 0))
        per_slot.append({
            "slot": slot,
            "logged_in": slot in actives,
            "counts": c,
        })
    healthy_pct = round(totals["healthy"] / totals["assigned"] * 100, 1) if totals["assigned"] else 0.0
    return {
        "totals": totals,
        "healthy_pct": healthy_pct,
        "logged_in_accounts": len(actives),
        "per_slot": per_slot,
    }
@router.post("/groups/update")
async def update_groups(payload: dict):
    raw = payload.get("groups", [])
    mode = (str(payload.get("mode") or "merge")).strip().lower()
    if mode not in ("merge", "replace"):
        mode = "merge"

    uploaded, skipped_invalid_format = _parse_uploaded_groups(raw)
    if not uploaded:
        return {
            "success": False,
            "error": "No valid groups found",
            "skipped_invalid_format": skipped_invalid_format,
            "mode": mode,
        }

    ensure_invalid_registry_backfill()
    try:
        master = load_master_groups(strict=True)
    except ValueError as e:
        return {
            "success": False,
            "error": str(e),
            "skipped_invalid_format": skipped_invalid_format,
            "mode": mode,
        }
    all_dead = collect_all_dead_for_upload()
    previous_total = len(master)
    old_set = set(master)

    skipped_dead = 0
    if mode == "replace":
        merged = []
        seen_keys: set[str] = set()
        for g in uploaded:
            key = _normalize_group_name(g)
            if key in all_dead:
                skipped_dead += 1
                continue
            if key in seen_keys:
                continue
            seen_keys.add(key)
            merged.append(g)

        backup_path = None
        if master:
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_path = os.path.join(
                DATA_DIR, f"groups_list_backup_{len(master)}_{ts}.json"
            )
            try:
                with open(backup_path, "w", encoding="utf-8") as f:
                    json.dump(master, f, indent=2)
            except Exception:
                backup_path = None

        save_master_groups(merged)
        new_set = set(merged)
        await _push_state()
        return {
            "success": True,
            "mode": "replace",
            "total": len(merged),
            "previous_total": previous_total,
            "removed_from_old": len(old_set - new_set),
            "kept_from_old": len(old_set & new_set),
            "added_new": len(new_set - old_set),
            "already_existed": 0,
            "skipped_invalid_format": skipped_invalid_format,
            "skipped_dead": skipped_dead,
            "backup_path": backup_path,
            "groups": merged,
        }

    merged = list(master)
    existing_norm = {_normalize_group_name(g): g for g in master}
    added = 0
    for g in uploaded:
        if _normalize_group_name(g) in all_dead:
            skipped_dead += 1
            continue
        key = _normalize_group_name(g)
        if key in existing_norm:
            continue
        merged.append(g)
        existing_norm[key] = g
        added += 1

    save_master_groups(merged)
    await _push_state()
    return {
        "success": True,
        "mode": "merge",
        "total": len(merged),
        "previous_total": previous_total,
        "removed_from_old": 0,
        "added_new": added,
        "already_existed": len(uploaded) - added - skipped_dead,
        "skipped_invalid_format": skipped_invalid_format,
        "skipped_dead": skipped_dead,
        "groups": merged,
    }
