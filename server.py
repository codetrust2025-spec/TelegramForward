"""
FastAPI entrypoint — thin API layer.
Execution lives in workers/ and features/ only.
Accounts run independently; no rotation scheduler.
"""

import asyncio
import json
import os
import shutil
from datetime import datetime

from fastapi import FastAPI, File, Form, Query, UploadFile, WebSocket, WebSocketDisconnect
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
from core.account_info_store import clear_account_info, load_account_info, save_account_info
from core.login_pending import clear_pending, load_pending, save_pending
from core.worker_persistence import log_reload_event
from services.account_manager import manager
from events.event_bus import event_bus
from events.event_types import EventType

from core.dashboard_auth_api import install_dashboard_auth
from core.dashboard_auth_vps import _API_ROOTS

registry = manager  # backward-compatible alias

app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
install_dashboard_auth(app)

# Per-slot login state — no cross-account coupling
login_state: dict[str, dict] = {
    slot: {"phone": None, "phone_code_hash": None} for slot in ACCOUNTS
}


def _sync_login_state_slots() -> None:
    """Ensure login_state has an entry for every configured account slot."""
    for slot in ACCOUNTS:
        login_state.setdefault(slot, {"phone": None, "phone_code_hash": None})


def _slot_valid(slot: str) -> bool:
    return slot in ACCOUNTS


def _get_login_pending(slot: str) -> dict | None:
    """Memory first, then disk — survives uvicorn auto-reload between send & verify."""
    ls = login_state.get(slot) or {}
    if ls.get("phone") and ls.get("phone_code_hash"):
        return ls
    disk = load_pending(slot)
    if disk:
        login_state[slot] = disk
        return disk
    return None


async def _ensure_login_client(slot: str) -> TelegramClient:
    """Login/verify client — never opens a second SQLite session while one exists."""
    telegram_client.set_login_exclusive(slot, True)
    return await telegram_client.get_login_client(slot)


async def _prepare_login_slot(slot: str) -> None:
    """Stop worker and clear session files; OTP uses in-memory StringSession only."""
    await telegram_client.quiesce_slot_for_login(slot)


def _first_logged_in_slot(exclude: str | None = None) -> str | None:
    for slot in ACCOUNT_SLOTS:
        if exclude and slot == exclude:
            continue
        if registry.get_worker(slot).state.account_info:
            return slot
    return None


def _migrate_legacy_files() -> None:
    """One-time copy of root-level data files into data/."""
    os.makedirs(DATA_DIR, exist_ok=True)
    legacy_groups = os.path.join(BASE_DIR, "groups_list.json")
    legacy_msg = os.path.join(BASE_DIR, "custom_message.txt")
    if os.path.exists(legacy_groups) and not os.path.exists(GROUPS_FILE):
        shutil.copy2(legacy_groups, GROUPS_FILE)
    if os.path.exists(legacy_msg) and not os.path.exists(MESSAGE_FILE):
        shutil.copy2(legacy_msg, MESSAGE_FILE)
    ensure_groups_loaded()


async def _push_state() -> None:
    await broadcast.broadcast({"type": "state", **registry.build_ui_state()})


# ── WebSocket ─────────────────────────────────────────────────────────────────

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    broadcast.active_connections.append(websocket)
    await websocket.send_json({"type": "state", **registry.build_ui_state()})
    if _membership_scheduler is not None:
        _membership_scheduler.schedule_stale_refresh(reason="dashboard_open")
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        if websocket in broadcast.active_connections:
            broadcast.active_connections.remove(websocket)


CODE_VERSION = "2026-05-23-account-isolation"
_persist_running_task: asyncio.Task | None = None
_health_monitor = None
_membership_scheduler = None
_start_all_task: asyncio.Task | None = None


async def _bootstrap_missing_joined_counts() -> None:
    """First login / stale membership: queue joined-count scan when needed."""
    from core.account_info_store import load_account_info
    from core.join_cycle import load_join_state
    from datetime import datetime, timezone

    def _needs_membership_rescan(slot: str, info: dict) -> bool:
        if info.get("joined_total") is None:
            return True
        js = load_join_state(slot)
        last_join = js.get("last_new_join_at")
        if not last_join:
            return False
        updated = info.get("joined_updated_at")
        if not updated:
            return True
        try:
            lj = datetime.fromisoformat(str(last_join).replace("Z", "+00:00"))
            up = datetime.strptime(str(updated), "%Y-%m-%d %H:%M UTC").replace(
                tzinfo=timezone.utc
            )
            return lj > up
        except Exception:
            return False

    await asyncio.sleep(8.0)
    for slot in ACCOUNTS:
        if telegram_client.any_login_exclusive():
            return
        w = registry.get_worker(slot)
        info = w.state.account_info or load_account_info(slot)
        if not info or not info.get("phone"):
            continue
        if not _needs_membership_rescan(slot, info):
            continue
        if w.state.running:
            w.request_joined_scan()
            continue
        try:
            await registry.refresh_joined_counts(slot)
            await _push_state()
        except Exception:
            pass
        await asyncio.sleep(6.0)


async def _persist_running_workers_loop() -> None:
    """Heartbeat: save running workers so reload survives abrupt shutdown."""
    from core.worker_persistence import save_running_slots

    while True:
        try:
            await asyncio.sleep(30)
            running = [
                s
                for s, runtime in registry.all_runtimes().items()
                if runtime.worker.state.running
            ]
            if running:
                save_running_slots(running)
        except asyncio.CancelledError:
            break
        except Exception:
            pass


async def _startup_background() -> None:
    """Telethon refresh + worker resume — must not block HTTP/WebSocket."""
    from core.worker_persistence import log_reload_event

    try:
        await _push_state()
        await registry.refresh_all_info()
        await _push_state()
        await asyncio.sleep(1.0)
        resumed = await registry.resume_persisted_workers()
        if resumed:
            log_reload_event(f"Auto-resumed workers after reload: {', '.join(resumed)}")
            await _push_state()
        asyncio.create_task(_bootstrap_missing_joined_counts())
        from services.dm_inbox_service import ensure_inbox_listeners

        async def _inbox_listeners_after_workers() -> None:
            await asyncio.sleep(3.0)
            await ensure_inbox_listeners()

        asyncio.create_task(_inbox_listeners_after_workers())

        async def _inbox_periodic_sync() -> None:
            from core.config import ACCOUNTS
            from services.dm_inbox_service import (
                ensure_inbox_listener,
                sync_stored_conversations,
            )

            await asyncio.sleep(12.0)
            while True:
                if telegram_client.any_login_exclusive():
                    await asyncio.sleep(5.0)
                    continue
                for slot in ACCOUNTS:
                    try:
                        await ensure_inbox_listener(slot)
                        await sync_stored_conversations(
                            slot, per_chat_limit=12, max_chats=6
                        )
                    except Exception:
                        pass
                    await asyncio.sleep(2.0)
                await asyncio.sleep(30.0)

        asyncio.create_task(_inbox_periodic_sync())
    except Exception as e:
        log_reload_event(f"Startup background task error: {type(e).__name__}: {e}")


@app.on_event("startup")
async def startup():
    global _persist_running_task, _health_monitor, _membership_scheduler
    _sync_login_state_slots()
    telegram_client.sync_slots()
    _migrate_legacy_files()
    manager.set_on_change(_push_state)
    event_bus.set_state_push(_push_state)

    from events.subscribers import register_event_subscribers

    register_event_subscribers()

    from core.auto_reload import log_process_start

    log_process_start(version=CODE_VERSION)

    for slot in ACCOUNTS:
        cached = load_account_info(slot)
        if cached:
            registry.get_worker(slot).state.account_info = cached

    _persist_running_task = asyncio.create_task(_persist_running_workers_loop())
    asyncio.create_task(_startup_background())

    from core.health_monitor import HealthMonitor

    _health_monitor = HealthMonitor(manager)
    manager.set_health_monitor(_health_monitor)
    _health_monitor.start()

    from core.joined_membership_scheduler import JoinedMembershipScheduler

    _membership_scheduler = JoinedMembershipScheduler(manager, _push_state)
    _membership_scheduler.start()


@app.on_event("shutdown")
async def shutdown():
    """Graceful shutdown — persist workers, disconnect Telethon, resume after reload."""
    global _persist_running_task, _health_monitor, _membership_scheduler

    if _membership_scheduler is not None:
        await _membership_scheduler.stop()
        _membership_scheduler = None

    if _health_monitor is not None:
        await _health_monitor.stop()
        _health_monitor = None

    if _persist_running_task is not None:
        _persist_running_task.cancel()
        try:
            await _persist_running_task
        except asyncio.CancelledError:
            pass
        _persist_running_task = None

    from core.auto_reload import log_process_shutdown, reload_enabled
    from core.system_lifecycle import graceful_shutdown

    running = await graceful_shutdown(registry)
    if reload_enabled():
        log_process_shutdown(running_workers=running)


# ── Forwarding control (per-account independent) ──────────────────────────────

async def _start_all_background(one_shot: bool = False) -> None:
    global _start_all_task
    try:
        started = await registry.start_all_logged_in(one_shot=one_shot)
        if started:
            await _push_state()
    finally:
        _start_all_task = None


@app.post("/start")
async def start_all():
    """Queue start for every logged-in account; return immediately for UI responsiveness."""
    global _start_all_task
    if _start_all_task is not None and not _start_all_task.done():
        return {"status": "queued", "accounts": [], "message": "Start all already in progress"}
    if not any(registry.get_runtime(slot).has_login() for slot in ACCOUNTS):
        return {"status": "error", "accounts": [], "message": "No logged-in accounts"}
    _start_all_task = asyncio.create_task(_start_all_background(one_shot=False))
    return {"status": "queued", "accounts": [], "message": "Starting logged-in accounts in background"}


@app.post("/start-test")
async def start_test_all():
    global _start_all_task
    if _start_all_task is not None and not _start_all_task.done():
        return {"status": "queued", "accounts": [], "message": "Start all already in progress"}
    if not any(registry.get_runtime(slot).has_login() for slot in ACCOUNTS):
        return {"status": "error", "accounts": [], "message": "No logged-in accounts"}
    _start_all_task = asyncio.create_task(_start_all_background(one_shot=True))
    return {"status": "queued", "accounts": [], "message": "Starting one test cycle in background"}


@app.post("/stop")
async def stop_all():
    registry.stop_all()
    await _push_state()
    return {"status": "stopped", **registry.build_ui_state()}


@app.post("/account/{slot}/start")
async def start_account(slot: str, one_shot: bool = Query(False)):
    if slot not in ACCOUNTS:
        return {"status": "error", "message": "Invalid slot"}
    if not await registry.start_account(slot, one_shot=one_shot):
        w = registry.get_worker(slot)
        if not w.state.account_info:
            return {"status": "error", "message": f"{slot} not logged in"}
        return {"status": "already_running"}
    await _push_state()
    return {"status": "started", "slot": slot}


@app.post("/account/{slot}/stop")
async def stop_account(slot: str):
    if slot not in ACCOUNTS:
        return {"status": "error", "message": "Invalid slot"}
    await registry.stop_account(slot)
    await _push_state()
    return {"status": "stopped", "slot": slot, **registry.build_ui_state()}


@app.post("/account/{slot}/restart")
async def restart_account(slot: str):
    if slot not in ACCOUNTS:
        return {"status": "error", "message": "Invalid slot"}
    ok = await manager.restart_account(slot)
    await _push_state()
    return {"status": "restarted" if ok else "error", "slot": slot, **registry.build_ui_state()}


@app.post("/account/{slot}/clear-logs")
async def clear_account_logs(slot: str):
    if slot not in ACCOUNTS:
        return {"status": "error", "message": "Invalid slot"}
    await registry.clear_logs(slot)
    await _push_state()
    return {"status": "cleared", "slot": slot, **registry.build_ui_state()}


@app.get("/state")
async def get_state():
    return registry.build_ui_state()


@app.get("/account/{slot}/status")
async def account_status(slot: str):
    if slot not in ACCOUNTS:
        return {"status": "error", "message": "Invalid slot"}
    return {"status": "ok", **manager.get_status(slot)}


@app.get("/metrics")
async def fleet_metrics():
    from core.fleet_rate_coordinator import fleet_rate_coordinator
    from core.observability.account_metrics import metrics_store

    return {
        "status": "ok",
        "metrics": metrics_store.all_snapshots(),
        "fleet_rate": fleet_rate_coordinator.snapshot(),
    }


@app.get("/metrics/{slot}")
async def account_metrics(slot: str):
    if slot not in ACCOUNTS:
        return {"status": "error", "message": "Invalid slot"}
    from core.observability.account_metrics import metrics_store

    return {"status": "ok", "metrics": metrics_store.snapshot(slot)}


@app.get("/alerts")
async def fleet_alerts(limit: int = Query(50, ge=1, le=200)):
    from core.observability.alerts import alert_store

    return {"status": "ok", "alerts": alert_store.recent(limit=limit)}


@app.get("/stats/daily")
async def get_daily_stats():
    from core.daily_stats import compute_daily_stats

    return {"status": "ok", "daily_stats": compute_daily_stats(list(ACCOUNTS))}


@app.post("/stats/reset")
async def reset_stats(payload: dict | None = None):
    """Manual mid-day reset; default daily window is midnight IST → now."""
    return await _perform_stats_reset(payload or {})


@app.post("/stats/reset-24h")
async def reset_daily_stats_24h():
    """Alias for global stats reset (backward compatible)."""
    return await _perform_stats_reset({})


async def _perform_stats_reset(payload: dict):
    from core.daily_stats import compute_daily_stats
    from core.send_stats import invalidate_cache
    from core.stats_reset import (
        StatsResetDebounced,
        get_reset_at_iso,
        set_reset_timestamp,
    )
    from core.join_cycle import daily_join_count_for_reset, join_stats_for_ui
    import services.crm_service as crm_service

    scope = (payload.get("scope") or "global").strip().lower()
    account_id = payload.get("account_id")

    if scope == "account":
        if not account_id or account_id not in ACCOUNTS:
            return {"status": "error", "error": "invalid_account"}
    else:
        account_id = None

    reset_slots = [account_id] if account_id else list(ACCOUNTS)
    join_baselines = {
        slot: daily_join_count_for_reset(slot)
        for slot in reset_slots
        if slot
    }

    try:
        ts = set_reset_timestamp(account_id=account_id, join_baselines=join_baselines)
    except StatsResetDebounced:
        return {
            "status": "error",
            "error": "reset_too_soon",
            "message": "Please wait before resetting stats again.",
        }

    invalidate_cache(account_id)
    fresh_stats = compute_daily_stats(list(ACCOUNTS))
    reset_scope = account_id or "global"

    await event_bus.publish(
        EventType.STATS_RESET,
        reset_scope,
        {
            "reset_timestamp": ts,
            "reset_at": get_reset_at_iso(account_id),
            "account_id": account_id,
            "scope": "account" if account_id else "global",
            "daily_stats": fresh_stats,
        },
        push_state=True,
        broadcast_ws=True,
    )

    await broadcast.broadcast({"type": "daily_stats", "daily_stats": fresh_stats})
    await broadcast.broadcast({"type": "crm", "crm": crm_service.build_crm_payload()})

    return {
        "status": "ok",
        "reset_timestamp": ts,
        "reset_at": get_reset_at_iso(account_id),
        "scope": reset_scope,
        "daily_stats": fresh_stats,
        # Join counters only — do not return full UI state (would overwrite client logs).
        "account_states": {
            slot: {"join_stats": join_stats_for_ui(slot)}
            for slot in reset_slots
            if slot
        },
    }


@app.post("/accounts/restore-sessions")
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


@app.get("/accounts")
async def list_accounts():
    """Account slots configured on this server (use for dashboard before WebSocket connects)."""
    from core.account_info_store import load_account_info
    from core.subscription_accounts import compute_subscription_slots, enrich_account_info

    info_map = {
        s: enrich_account_info(s, load_account_info(s))
        for s in ACCOUNTS
    }

    return {
        "account_slots": list(ACCOUNT_SLOTS),
        "subscription_slots": compute_subscription_slots(info_map),
        "count": len(ACCOUNT_SLOTS),
        "code_version": CODE_VERSION,
    }


@app.get("/health")
async def health():
    return {"status": "ok"}


# ── Groups (API-only writes to master list) ─────────────────────────────────

@app.get("/groups")
async def get_groups():
    groups = load_master_groups()
    return {"groups": groups, "total": len(groups)}


@app.get("/groups/removed")
async def get_removed_groups():
    invalid, blocked = set(), set()
    for slot in ACCOUNTS:
        inv, blk = load_account_dead(slot)
        invalid |= inv
        blocked |= blk
    return {"invalid": sorted(invalid), "blocked": sorted(blocked)}


@app.get("/groups/lists")
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


@app.get("/groups/health")
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


@app.get("/groups/total-list")
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
            details = await asyncio.wait_for(
                run_with_string_session(slot, fetch_joined_dialog_details, attempts=2),
                timeout=200,
            )
        except Exception as e_ss:
            try:
                await release_session(slot, wait=1.5)
                details = await asyncio.wait_for(
                    run_group_operation(slot, _op, attempts=2),
                    timeout=200,
                )
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


@app.get("/groups/health-summary")
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


def _parse_uploaded_groups(raw: list) -> tuple[list[str], int]:
    uploaded, seen = [], set()
    skipped_invalid_format = 0
    for g in raw:
        norm = normalize_upload_username(str(g))
        if not norm:
            skipped_invalid_format += 1
            continue
        if not is_valid_group_username(norm):
            skipped_invalid_format += 1
            continue
        key = _normalize_group_name(norm)
        if key not in seen:
            seen.add(key)
            uploaded.append(norm)
    return uploaded, skipped_invalid_format


@app.post("/groups/update")
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


# ── Message ───────────────────────────────────────────────────────────────────

@app.get("/message")
async def get_message(slot: str | None = None):
    if slot and slot in ACCOUNTS:
        return {
            "message": load_message_for_account(slot),
            "slot": slot,
            "rewrite_enabled": MESSAGE_REWRITE_ENABLED,
        }
    return {"message": load_message(), "rewrite_enabled": MESSAGE_REWRITE_ENABLED}


@app.get("/message/preview")
async def message_preview(slot: str, cycle: int = 1):
    if slot not in ACCOUNTS:
        return {"success": False, "error": "Invalid slot"}
    return {"success": True, **preview_cycle_message(slot, max(1, cycle))}


@app.post("/message")
async def update_message(payload: dict):
    text = payload.get("message", "").strip()
    slot = payload.get("slot")
    if not text:
        return {"success": False, "error": "Message cannot be empty"}
    if slot and slot in ACCOUNTS:
        save_message_for_account(slot, text)
    else:
        save_message(text)
    await _push_state()
    return {"success": True, "slot": slot}


# ── Account UI helpers ────────────────────────────────────────────────────────

@app.post("/account/switch")
async def switch_account(payload: dict):
    slot = payload.get("slot")
    if slot not in ACCOUNTS:
        return {"success": False, "error": "Invalid slot"}
    registry.active_account = slot
    await _push_state()
    return {"success": True, "active_account": slot}


@app.get("/account/status")
async def account_status():
    info = await registry.refresh_all_info()
    return {
        "active_account": registry.active_account,
        "account_info": info,
    }


@app.post("/account/refresh-joined")
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
        return resp
    except Exception as e:
        return {"success": False, "error": str(e)}


# ── Login (per-slot isolated state) ───────────────────────────────────────────

@app.post("/login/send-otp")
async def send_otp(payload: dict):
    phone = payload.get("phone", "").strip()
    slot = payload.get("slot", "account1")
    if not phone:
        return {"success": False, "error": "Phone number required"}
    _sync_login_state_slots()
    if not _slot_valid(slot):
        return {"success": False, "error": "Invalid slot — restart backend (python scripts/dev.py)"}
    try:
        await _prepare_login_slot(slot)

        async def _send_code():
            c = await telegram_client.get_login_client(slot)
            return await c.send_code_request(phone)

        result = await telegram_client.run_login_with_retry(slot, _send_code)
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
    except Exception as e:
        clear_pending(slot)
        await telegram_client.finalize_login_exclusive(slot)
        err = str(e)
        if "database is locked" in err.lower():
            err = "Session file was busy. Wait 10 seconds, then tap Send OTP again."
        return {"success": False, "error": err}


@app.post("/login/verify-otp")
async def verify_otp(payload: dict):
    code = payload.get("code", "").strip()
    slot = (payload.get("slot") or "").strip()
    if not slot or slot not in ACCOUNTS:
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
        await telegram_client.commit_login_session(slot)
        from core.account_info_store import build_info_from_me

        from core.subscription_accounts import enrich_account_info

        info = enrich_account_info(slot, build_info_from_me(me))
        login_state[slot] = {"phone": None, "phone_code_hash": None}
        clear_pending(slot)

        worker_started = await registry.complete_login(slot, info)
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


@app.post("/login/logout")
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


# ── DM Inbox (private chats only — independent of forwarding workers) ─────────

@app.post("/inbox/listeners/refresh")
async def inbox_ensure_listeners():
    """Re-attach Telethon DM listeners (after reload or if live messages stop)."""
    from services.dm_inbox_service import bootstrap_listeners

    await bootstrap_listeners(force=True)
    return {"status": "ok", "message": "DM listeners re-attached"}


@app.post("/inbox/{slot}/sync/{user_id}")
async def inbox_force_sync(slot: str, user_id: int):
    """Pull latest messages from Telegram for one chat (bypasses UI)."""
    if slot not in ACCOUNTS:
        return {"status": "error", "message": "Invalid slot"}
    from core.dm_store import get_messages
    from services.dm_inbox_service import sync_conversation_from_telegram

    added = await sync_conversation_from_telegram(slot, user_id, limit=80)
    return {
        "status": "ok",
        "added": len(added),
        "messages": get_messages(slot, user_id),
    }


@app.get("/inbox")
async def inbox_all(
    slot: str | None = Query(None),
    combined: bool = Query(False),
    sync: bool = Query(False),
):
    from services import dm_inbox_service

    if sync:
        for s in ACCOUNTS:
            try:
                await dm_inbox_service.sync_stored_conversations(s)
            except Exception:
                pass

    if slot:
        if slot not in ACCOUNTS:
            return {"status": "error", "message": "Invalid slot"}
        return {"status": "ok", **dm_inbox_service.build_slot_payload(slot)}
    if combined:
        return {
            "status": "ok",
            "combined": True,
            "conversations": dm_inbox_service.get_combined_conversations(),
        }
    return {"status": "ok", **dm_inbox_service.build_all_inboxes()}


@app.get("/inbox/{slot}/messages/{user_id}")
async def inbox_messages(
    slot: str,
    user_id: int,
    sync: bool = Query(True),
):
    if slot not in ACCOUNTS:
        return {"status": "error", "message": "Invalid slot"}
    import asyncio

    from core.dm_store import get_messages
    from services import dm_inbox_service

    from core.dm_store import load_inbox

    messages = get_messages(slot, user_id)
    if sync:
        try:
            await dm_inbox_service.sync_read_receipts(slot, user_id)
        except Exception:
            pass
        try:
            await asyncio.wait_for(
                dm_inbox_service.sync_conversation_from_telegram(slot, user_id),
                timeout=15.0,
            )
            messages = get_messages(slot, user_id)
        except asyncio.TimeoutError:
            pass
        except Exception:
            pass
        # Only auto-mark-read on the explicit sync path. The fast (sync=0) path
        # is a passive preview; the front-end calls POST /inbox/{slot}/read/{user_id}
        # once the user has actually viewed the chat.
        key = str(user_id)
        had_unread = int(
            load_inbox(slot).get("conversations", {}).get(key, {}).get("unread_count") or 0
        ) > 0
        if had_unread:
            await dm_inbox_service.mark_read(slot, user_id)
    return {"status": "ok", "slot": slot, "user_id": user_id, "messages": messages}


@app.post("/inbox/{slot}/reply")
async def inbox_reply(slot: str, body: dict):
    if slot not in ACCOUNTS:
        return {"status": "error", "message": "Invalid slot"}
    user_id = body.get("user_id")
    text = body.get("text") or body.get("message") or ""
    # Track who composed this outbound message: "manual" (operator typed
    # from scratch) or "ai_approved" (operator clicked Suggest, then Send).
    # Other values are ignored and fall back to "manual" so callers can't
    # spoof exotic provenance.
    sent_by_raw = (body.get("sent_by") or "manual").strip().lower()
    sent_by = sent_by_raw if sent_by_raw in {"manual", "ai_approved"} else "manual"
    if user_id is None:
        return {"status": "error", "message": "user_id required"}
    try:
        from messaging.message_router import message_router

        result = await message_router.enqueue_dm_send(
            slot, int(user_id), str(text), wait=True, sent_by=sent_by,
        )
        from services.crm_service import enrich_conversation, get_lead

        conv = result.get("conversation") or {}
        uid = int(user_id)
        summary = enrich_conversation(
            slot,
            {
                "user_id": uid,
                "username": conv.get("username") or "",
                "name": conv.get("name") or "",
                "last_message": conv.get("last_message") or "",
                "last_message_at": conv.get("last_message_at"),
                "unread_count": conv.get("unread_count") or 0,
            },
        )
        lead = get_lead(slot, uid)
        return {
            "status": "ok",
            "message": result.get("message"),
            "conversation": summary,
            "lead": lead,
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}


@app.get("/ai/smart-reply/config")
async def ai_smart_reply_get_config():
    from core import ai_smart_reply
    from core.ai_smart_reply_store import get_config

    return {
        "status": "ok",
        "config": get_config(),
        "health": ai_smart_reply.health(),
    }


@app.post("/ai/smart-reply/config")
async def ai_smart_reply_update_config(body: dict):
    from core import ai_smart_reply
    from core.ai_smart_reply_store import update_config

    patch = {k: v for k, v in (body or {}).items() if v is not None}
    cfg = update_config(**patch)
    return {
        "status": "ok",
        "config": cfg,
        "health": ai_smart_reply.health(),
    }


@app.post("/ai/smart-reply/leads/{slot}/{user_id}/toggle")
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


@app.get("/ai/smart-reply/leads/{slot}/{user_id}")
async def ai_smart_reply_lead_state(slot: str, user_id: int):
    if slot not in ACCOUNTS:
        return {"status": "error", "message": "Invalid slot"}
    from core.ai_smart_reply_store import get_lead_state

    return {"status": "ok", "lead_state": get_lead_state(slot, int(user_id))}


@app.post("/ai/smart-reply/assess")
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


@app.get("/ai/smart-reply/assessment")
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


@app.post("/ai/smart-reply/manual-approval")
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


@app.post("/inbox/{slot}/ai-reply")
@app.post("/inbox/{slot}/ai-suggestion")
async def inbox_ai_suggestion(slot: str, body: dict):
    """Generate an AI draft reply for the latest inbound message — but DO
    NOT send it. The frontend fills the reply composer with the draft so
    the operator can review, edit, and click Send themselves.

    Both `/ai-reply` and `/ai-suggestion` route here; `/ai-reply` is kept
    as an alias so older clients keep working — they too will now only
    get a suggestion back, never an automatic send.

    Response shape:
        {
          "status": "ok",
          "text":   "<draft>",
          "stage":  "...",
          "confidence": 0.82,
          "ai": True
        }
    """
    if slot not in ACCOUNTS:
        return {"status": "error", "message": "Invalid slot"}
    user_id = body.get("user_id")
    if user_id is None:
        return {"status": "error", "message": "user_id required"}
    from core import ai_smart_reply
    from core.dm_store import load_inbox

    conv = (load_inbox(slot).get("conversations") or {}).get(str(int(user_id))) or {}
    msgs = list(conv.get("messages") or [])
    last_in = next((m for m in reversed(msgs) if m.get("direction") == "in"), None)
    if not last_in:
        return {"status": "error", "message": "No inbound message in this chat"}
    if not ai_smart_reply.is_enabled():
        return {"status": "error", "message": "AI smart-reply is disabled or API key missing"}

    res = await ai_smart_reply.generate_suggestion(
        slot,
        int(user_id),
        user_message_id=last_in.get("id"),
        user_text=last_in.get("text") or "",
    )
    if not res.get("ok"):
        return {"status": "error", "message": res.get("error") or res.get("reason") or "ai_failed", **res}
    return {"status": "ok", **res}


@app.post("/inbox/{slot}/send-location")
async def inbox_send_location(slot: str, body: dict):
    """Send a geo location pin to a DM recipient from the given account slot.

    Body: { user_id: int, latitude: float, longitude: float, accuracy?: float }
    """
    if slot not in ACCOUNTS:
        return {"status": "error", "message": "Invalid slot"}
    user_id = body.get("user_id")
    latitude = body.get("latitude")
    longitude = body.get("longitude")
    accuracy = body.get("accuracy")
    if user_id is None:
        return {"status": "error", "message": "user_id required"}
    if latitude is None or longitude is None:
        return {"status": "error", "message": "latitude and longitude required"}
    try:
        from messaging.message_router import message_router

        result = await message_router.enqueue_dm_send_location(
            slot,
            int(user_id),
            float(latitude),
            float(longitude),
            accuracy=float(accuracy) if accuracy is not None else None,
            wait=True,
        )
        from services.crm_service import enrich_conversation, get_lead

        conv = result.get("conversation") or {}
        uid = int(user_id)
        summary = enrich_conversation(
            slot,
            {
                "user_id": uid,
                "username": conv.get("username") or "",
                "name": conv.get("name") or "",
                "last_message": conv.get("last_message") or "",
                "last_message_at": conv.get("last_message_at"),
                "unread_count": conv.get("unread_count") or 0,
            },
        )
        lead = get_lead(slot, uid)
        return {
            "status": "ok",
            "message": result.get("message"),
            "conversation": summary,
            "lead": lead,
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}


@app.patch("/inbox/{slot}/messages/{user_id}/{message_id}")
async def inbox_edit_message(slot: str, user_id: int, message_id: int, body: dict):
    if slot not in ACCOUNTS:
        return {"status": "error", "message": "Invalid slot"}
    text = body.get("text") or body.get("message") or ""
    if not str(text).strip():
        return {"status": "error", "message": "text required"}
    try:
        from services import dm_inbox_service

        result = await dm_inbox_service.run_dm_edit(
            slot, int(user_id), int(message_id), str(text),
        )
        return {
            "status": "ok",
            "message": result.get("message"),
            "conversation": result.get("conversation"),
            "unchanged": bool(result.get("unchanged")),
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}


@app.post("/inbox/{slot}/read/{user_id}")
async def inbox_mark_read(slot: str, user_id: int):
    if slot not in ACCOUNTS:
        return {"status": "error", "message": "Invalid slot"}
    from services import dm_inbox_service

    await dm_inbox_service.mark_read(slot, int(user_id))
    return {"status": "ok", "slot": slot, "user_id": user_id}


# ── CRM (lead management on top of inbox) ─────────────────────────────────────

@app.get("/crm/state")
async def crm_state():
    from services import crm_service

    crm_service.sync_leads_from_inbox()
    return {"status": "ok", **crm_service.build_crm_payload()}


@app.get("/crm/leads/{slot}/{user_id}")
async def crm_get_lead(slot: str, user_id: int):
    if slot not in ACCOUNTS:
        return {"status": "error", "message": "Invalid slot"}
    from services import crm_service

    lead = crm_service.get_lead_detail(slot, user_id)
    if not lead:
        return {"status": "error", "message": "Lead not found"}
    return {"status": "ok", "lead": lead}


@app.patch("/crm/leads/{slot}/{user_id}")
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


@app.post("/crm/leads/{slot}/{user_id}/mark-handled")
async def crm_mark_handled(slot: str, user_id: int):
    if slot not in ACCOUNTS:
        return {"status": "error", "message": "Invalid slot"}
    from services import crm_service

    try:
        lead = await crm_service.mark_reply_handled(slot, int(user_id))
        return {"status": "ok", "lead": lead, "crm": crm_service.build_crm_payload()}
    except ValueError as e:
        return {"status": "error", "message": str(e)}


@app.post("/crm/leads/{slot}/{user_id}/follow-up")
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


@app.get("/crm/call-now/options")
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


@app.post("/crm/call-now")
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


@app.post("/crm/unblock")
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


@app.post("/crm/schedule-call")
async def crm_schedule_call_body(body: dict):
    """Schedule a call (flat payload: account_id, user_id, scheduled_time, call_type, notes)."""
    slot = body.get("account_id") or body.get("slot")
    user_id = body.get("user_id")
    if not slot or slot not in ACCOUNTS:
        return {"status": "error", "message": "Invalid account_id"}
    if user_id is None:
        return {"status": "error", "message": "user_id required"}
    return await _crm_schedule_call_impl(slot, int(user_id), body)


async def _crm_schedule_call_impl(slot: str, user_id: int, body: dict):
    from services import call_service, crm_service as _crm

    scheduled_time = body.get("scheduled_time")
    if not scheduled_time:
        return {"status": "error", "message": "scheduled_time required"}
    call_type = body.get("call_type") or "telegram"
    notes = body.get("notes") or ""
    try:
        call = await call_service.schedule_lead_call(
            slot,
            user_id,
            scheduled_time=str(scheduled_time),
            call_type=str(call_type),
            notes=str(notes),
        )
        lead = _crm.get_lead_detail(slot, user_id)
        return {"status": "ok", "call": call, "lead": lead, "crm": _crm.build_crm_payload()}
    except Exception as e:
        return {"status": "error", "message": str(e)}


@app.post("/crm/leads/{slot}/{user_id}/calls")
async def crm_schedule_call(slot: str, user_id: int, body: dict):
    if slot not in ACCOUNTS:
        return {"status": "error", "message": "Invalid slot"}
    return await _crm_schedule_call_impl(slot, int(user_id), body)


@app.post("/crm/leads/{slot}/{user_id}/calls/complete")
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


@app.get("/login/status")
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


# ── Candidates / Profiles tracker ───────────────────────────────────────────
# Replaces the old "Profiles list update Form" Google Sheet. All CRUD happens
# from the dashboard's Candidates tab and persists to data/candidates.json.

@app.get("/candidates")
async def candidates_list(
    stage: str | None = Query(default=None),
    task: str | None = Query(default=None),
    search: str | None = Query(default=None),
    month: str | None = Query(default=None),
    pending_only: bool = Query(default=False),
    reference: str | None = Query(default=None),
):
    from features import candidate_store

    rows = candidate_store.list_candidates(
        stage=stage, task=task, search=search, month=month,
        pending_only=pending_only, reference=reference,
    )
    return {"status": "ok", "candidates": rows, "count": len(rows)}


@app.get("/candidates/stats")
async def candidates_stats(month: str | None = Query(default=None)):
    from features import candidate_store

    return {"status": "ok", "stats": candidate_store.stats(month=month)}


@app.get("/candidates/{cid}")
async def candidates_get(cid: str):
    from features import candidate_store

    row = candidate_store.get_candidate(cid)
    if not row:
        return {"status": "error", "message": "Candidate not found"}
    return {"status": "ok", "candidate": row}


@app.post("/candidates")
async def candidates_create(body: dict):
    from features import candidate_store

    if not (body.get("name") or "").strip():
        return {"status": "error", "message": "Name is required"}
    row = candidate_store.create_candidate(body)
    return {"status": "ok", "candidate": row}


@app.patch("/candidates/{cid}")
async def candidates_update(cid: str, body: dict):
    from features import candidate_store

    row = candidate_store.update_candidate(cid, body or {})
    if not row:
        return {"status": "error", "message": "Candidate not found"}
    return {"status": "ok", "candidate": row}


@app.delete("/candidates/{cid}")
async def candidates_delete(cid: str):
    from features import candidate_store

    ok = candidate_store.delete_candidate(cid)
    if not ok:
        return {"status": "error", "message": "Candidate not found"}
    return {"status": "ok"}


# ── Payment proofs ──────────────────────────────────────────────────────────────

@app.post("/candidates/{cid}/proofs")
async def candidates_upload_proof(
    cid: str,
    file: UploadFile = File(...),
    note: str = Form(default=""),
):
    """Attach a payment screenshot (image) to a candidate.

    Multipart form fields:
      - `file`  (required): the screenshot itself.
      - `note`  (optional): a short caption (e.g. "₹10k UPI · 26 May").
    """
    from features import candidate_store

    try:
        raw = await file.read()
        entry = candidate_store.add_proof(
            cid,
            data=raw,
            original_name=file.filename or "",
            mime_type=file.content_type or "",
            note=note or "",
        )
    except ValueError as e:
        return {"status": "error", "message": str(e)}
    if entry is None:
        return {"status": "error", "message": "Candidate not found"}
    row = candidate_store.get_candidate(cid)
    return {"status": "ok", "proof": entry, "candidate": row}


@app.get("/candidates/{cid}/proofs/{pid}")
async def candidates_serve_proof(cid: str, pid: str):
    from features import candidate_store

    hit = candidate_store.get_proof(cid, pid)
    if hit is None:
        return {"status": "error", "message": "Proof not found"}
    path, entry = hit
    return FileResponse(
        path,
        media_type=entry.get("mime_type") or "application/octet-stream",
        filename=entry.get("original_name") or entry.get("filename"),
    )


@app.delete("/candidates/{cid}/proofs/{pid}")
async def candidates_delete_proof(cid: str, pid: str):
    from features import candidate_store

    ok = candidate_store.delete_proof(cid, pid)
    if not ok:
        return {"status": "error", "message": "Proof not found"}
    row = candidate_store.get_candidate(cid)
    return {"status": "ok", "candidate": row}


@app.patch("/candidates/{cid}/proofs/{pid}")
async def candidates_update_proof_note(cid: str, pid: str, body: dict):
    from features import candidate_store

    note = (body or {}).get("note", "")
    entry = candidate_store.update_proof_note(cid, pid, note)
    if entry is None:
        return {"status": "error", "message": "Proof not found"}
    return {"status": "ok", "proof": entry}


# ── Handler / reference expenses ────────────────────────────────────────────────

@app.get("/handler-expenses")
async def handler_expenses_list(
    reference: str | None = Query(default=None),
    month: str | None = Query(default=None),
):
    from features import handler_expenses

    rows = handler_expenses.list_expenses(reference=reference, month=month)
    total = sum(int(r.get("amount") or 0) for r in rows)
    return {
        "status": "ok",
        "expenses": rows,
        "count": len(rows),
        "total": total,
        "categories": handler_expenses.CATEGORY_LABELS,
        "available_months": handler_expenses.available_months(),
    }


@app.post("/handler-expenses")
async def handler_expenses_create(body: dict):
    from features import handler_expenses

    if not (body or {}).get("reference", "").strip():
        return {"status": "error", "message": "Reference (handler name) is required"}
    if int((body or {}).get("amount") or 0) <= 0:
        return {"status": "error", "message": "Amount must be greater than zero"}
    row = handler_expenses.create_expense(body or {})
    return {"status": "ok", "expense": row}


@app.patch("/handler-expenses/{eid}")
async def handler_expenses_update(eid: str, body: dict):
    from features import handler_expenses

    row = handler_expenses.update_expense(eid, body or {})
    if row is None:
        return {"status": "error", "message": "Expense not found"}
    return {"status": "ok", "expense": row}


@app.delete("/handler-expenses/{eid}")
async def handler_expenses_delete(eid: str):
    from features import handler_expenses

    ok = handler_expenses.delete_expense(eid)
    if not ok:
        return {"status": "error", "message": "Expense not found"}
    return {"status": "ok"}


@app.get("/handler-expenses/summary")
async def handler_expenses_summary(month: str | None = Query(default=None)):
    from features import handler_expenses

    summary = handler_expenses.summary_by_handler(month=month)
    total = sum(b["total"] for b in summary.values())
    return {
        "status": "ok",
        "summary": summary,
        "total": total,
        "count": sum(b["count"] for b in summary.values()),
    }


# ── Handler base salaries (hybrid pay model) ────────────────────────────────────
#
# A handler can be on a fixed monthly base salary (this) PLUS their 50%
# commission on every rupee a referred client pays (computed live from
# the candidates table). The hybrid total is what the Handler Payouts
# card and Top Performers chips already show.

@app.get("/handler-salaries")
async def handler_salaries_list(month: str | None = Query(default=None)):
    from features import handler_salaries
    rows = handler_salaries.list_salaries()
    by_handler = handler_salaries.salary_owed_by_handler(month=month)
    return {
        "status": "ok",
        "salaries": rows,
        "by_handler": by_handler,
        "total_for_view": handler_salaries.total_salary_owed(month=month),
        "month": month or "all",
    }


@app.post("/handler-salaries")
async def handler_salaries_upsert(body: dict):
    """Create or update one handler's monthly salary.

    Body: { reference, monthly_salary, active_from?, active_until? }
    Passing monthly_salary <= 0 clears the entry (same as DELETE).
    """
    from features import handler_salaries
    try:
        row = handler_salaries.set_salary(
            reference     = body.get("reference") or "",
            monthly_salary= body.get("monthly_salary") or 0,
            active_from   = body.get("active_from"),
            active_until  = body.get("active_until"),
        )
    except ValueError as e:
        return {"status": "error", "message": str(e)}
    return {"status": "ok", "salary": row}


@app.delete("/handler-salaries/{reference}")
async def handler_salaries_delete(reference: str):
    from features import handler_salaries
    removed = handler_salaries.delete_salary(reference)
    return {"status": "ok" if removed else "not_found", "reference": reference}


# ── Frontend (production) ───────────────────────────────────────────────────────

STATIC_DIR = os.path.join(os.path.dirname(__file__), "static")
if os.path.exists(STATIC_DIR):
    app.mount(
        "/assets",
        StaticFiles(directory=os.path.join(STATIC_DIR, "assets")),
        name="assets",
    )

    _NO_CACHE = {"Cache-Control": "no-cache, no-store, must-revalidate", "Pragma": "no-cache"}

    @app.get("/")
    async def serve_index():
        return FileResponse(
            os.path.join(STATIC_DIR, "index.html"),
            headers=_NO_CACHE,
        )

    @app.get("/{full_path:path}")
    async def serve_spa(full_path: str):
        # Never serve index.html for API-like paths (avoids JSON parse errors in the UI)
        first = full_path.split("/")[0] if full_path else ""
        if first in _API_ROOTS:
            from fastapi import HTTPException
            raise HTTPException(status_code=404, detail="Not Found")
        file_path = os.path.join(STATIC_DIR, full_path)
        if os.path.exists(file_path):
            return FileResponse(file_path)
        return FileResponse(
            os.path.join(STATIC_DIR, "index.html"),
            headers=_NO_CACHE,
        )
