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


def _load_project_dotenv() -> None:
    """Load .env into os.environ so PM2/uvicorn workers see AI_API_KEY etc."""
    env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
    if not os.path.isfile(env_path):
        return
    try:
        from dotenv import load_dotenv

        load_dotenv(env_path, override=False)
    except ImportError:
        with open(env_path, encoding="utf-8") as f:
            for raw in f:
                line = raw.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, _, val = line.partition("=")
                key = key.strip()
                if key and key not in os.environ:
                    os.environ[key] = val.strip().strip('"').strip("'")


_load_project_dotenv()

registry = manager  # backward-compatible alias

app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
install_admin_dashboard(app)

from core.dashboard_auth_api import install_dashboard_auth

install_dashboard_auth(app)

from core.voice_call_api import install_voice_call_routes

install_voice_call_routes(app)

from core.web_push_api import install_web_push_routes

install_web_push_routes(app)

from core.whatsapp_api import install_whatsapp_routes

install_whatsapp_routes(app)

from core.public_slot_api import install_public_slot_routes

install_public_slot_routes(app)

from core.demo_tools_api import install_demo_tools_routes

install_demo_tools_routes(app)

from core.recruitment_mail_api import install_recruitment_mail_routes

install_recruitment_mail_routes(app)


def _require_fleet_admin(request: Request) -> None:
    from core.dashboard_access import require_fleet_admin

    require_fleet_admin(request)


# Per-slot login state — no cross-account coupling
login_state: dict[str, dict] = {
    slot: {"phone": None, "phone_code_hash": None} for slot in ACCOUNTS
}


def _sync_login_state_slots() -> None:
    """Ensure login_state has an entry for every configured account slot."""
    from core.config import ACCOUNTS as live_accounts

    for slot in live_accounts:
        login_state.setdefault(slot, {"phone": None, "phone_code_hash": None})


def _slot_valid(slot: str) -> bool:
    from core.config import ACCOUNTS as live_accounts

    return slot in live_accounts


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
    state = await asyncio.to_thread(registry.build_ui_state)
    await broadcast.broadcast({"type": "state", **state})


# ── WebSocket ─────────────────────────────────────────────────────────────────

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    from core import dashboard_auth_vps as dash_auth

    await websocket.accept()
    broadcast.active_connections.append(websocket)
    profile = dash_auth.operator_profile_from_cookies(dict(websocket.cookies))
    broadcast.connection_profiles[websocket] = profile
    full = await asyncio.to_thread(registry.build_ui_state)
    await websocket.send_json({"type": "state", **full})
    if _membership_scheduler is not None:
        _membership_scheduler.schedule_stale_refresh(reason="dashboard_open")
    try:
        while True:
            raw = await websocket.receive_text()
            try:
                msg = json.loads(raw)
            except json.JSONDecodeError:
                continue
            if not isinstance(msg, dict) or msg.get("type") != "voice":
                continue
            action = str(msg.get("action") or "").strip().lower()
            session_id = str(msg.get("session_id") or "").strip()
            if not session_id:
                continue
            from core import voice_signaling
            from services import voice_call_service as voice_svc

            if action == "register":
                await voice_signaling.register_peer(session_id, "operator", websocket)
            elif action == "signal":
                signal = msg.get("signal") if isinstance(msg.get("signal"), dict) else {}
                await voice_svc.handle_operator_signal(session_id, signal)
    except WebSocketDisconnect:
        pass
    finally:
        broadcast.connection_profiles.pop(websocket, None)
        if websocket in broadcast.active_connections:
            broadcast.active_connections.remove(websocket)


CODE_VERSION = "2026-05-23-account-isolation"
_persist_running_task: asyncio.Task | None = None
_health_monitor = None
_membership_scheduler = None
_shutdown_monitor = None
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


async def _auto_stats_reset_loop() -> None:
    """Roll daily dashboard counters every 24h and push fresh state to clients."""
    from core.daily_stats import refresh_daily_stats
    from core.join_cycle import join_stats_for_ui
    from core.stats_reset import get_reset_at_iso

    await asyncio.sleep(30.0)
    while True:
        try:
            daily_stats, auto_reset = await asyncio.to_thread(
                refresh_daily_stats, list(ACCOUNTS)
            )
            if auto_reset:
                reset_slots = (
                    list(ACCOUNTS)
                    if auto_reset.scope == "global"
                    else list(auto_reset.account_ids)
                )
                if auto_reset.scope == "global":
                    registry.reset_stats_display_counters(None)
                else:
                    for slot in auto_reset.account_ids:
                        registry.reset_stats_display_counters(slot)
                account_states_patch = {
                    slot: registry.get_worker(slot).state.to_dict()
                    for slot in reset_slots
                }
                reset_scope = "global" if auto_reset.scope == "global" else auto_reset.account_ids[0]
                await event_bus.publish(
                    EventType.STATS_RESET,
                    reset_scope,
                    {
                        "reset_timestamp": auto_reset.reset_timestamp,
                        "reset_at": get_reset_at_iso(
                            None if auto_reset.scope == "global" else auto_reset.account_ids[0]
                        ),
                        "account_id": None if auto_reset.scope == "global" else auto_reset.account_ids[0],
                        "scope": auto_reset.scope,
                        "auto": True,
                        "daily_stats": daily_stats,
                        "account_states": account_states_patch,
                    },
                    push_state=True,
                    broadcast_ws=True,
                )
                await broadcast.broadcast({"type": "daily_stats", "daily_stats": daily_stats})
                await _push_state()
        except asyncio.CancelledError:
            break
        except Exception:
            pass
        await asyncio.sleep(60.0)


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
        asyncio.create_task(_auto_stats_reset_loop())
        from core.daily_briefing import scheduler_loop as daily_briefing_scheduler_loop
        asyncio.create_task(daily_briefing_scheduler_loop(), name="daily_ai_briefing_scheduler")

        try:
            from core.karthik_inbox_sweep import start as start_karthik_inbox_sweep

            start_karthik_inbox_sweep()
        except Exception as e:
            log_reload_event(f"Karthik inbox sweep start failed: {type(e).__name__}: {e}")

        try:
            from services.interview_reminder_loop import start_interview_reminder_loop

            start_interview_reminder_loop()
        except Exception as e:
            log_reload_event(f"Interview reminder loop start failed: {type(e).__name__}: {e}")
    except Exception as e:
        log_reload_event(f"Startup background task error: {type(e).__name__}: {e}")


def _repair_inbox_conversation_keys() -> None:
    """Idempotent: move phone_e164 inbox keys to numeric user_id keys."""
    from core.config import ACCOUNT_SLOTS
    from core.dm_store import repair_conversation_keys

    total = 0
    for slot in ACCOUNT_SLOTS:
        try:
            total += len(repair_conversation_keys(slot))
        except Exception:
            pass
    if total:
        from core.worker_persistence import log_reload_event

        log_reload_event(f"Inbox key repair: {total} conversation(s) fixed")


@app.on_event("startup")
async def startup():
    global _persist_running_task, _health_monitor, _membership_scheduler
    from core.config import warn_default_telegram_creds

    warn_default_telegram_creds()
    from core.recruitment_mail_store import ensure_schema as ensure_recruitment_mail_schema
    ensure_recruitment_mail_schema()
    _repair_inbox_conversation_keys()
    _sync_login_state_slots()
    telegram_client.sync_slots()
    _migrate_legacy_files()
    manager.set_on_change(_push_state)
    event_bus.set_state_push(_push_state)
    from services.forward_message_service import forward_message_service

    forward_message_service.set_on_change(_push_state)
    forward_message_service.recover_jobs_after_restart()

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

    try:
        from core.karthik_inbox_sweep import start as start_karthik_inbox_sweep

        start_karthik_inbox_sweep()
    except Exception as e:
        log_reload_event(f"Karthik inbox sweep start failed: {type(e).__name__}: {e}")

    global _shutdown_monitor
    from core.account_shutdown_monitor import AccountShutdownMonitor

    _shutdown_monitor = AccountShutdownMonitor(manager)
    _shutdown_monitor.start()

    from workers.recruitment_mail_worker import recruitment_mail_worker
    recruitment_mail_worker.start()


@app.on_event("shutdown")
async def shutdown():
    """Graceful shutdown — persist workers, disconnect Telethon, resume after reload."""
    global _persist_running_task, _health_monitor, _membership_scheduler, _shutdown_monitor

    from workers.recruitment_mail_worker import recruitment_mail_worker
    await recruitment_mail_worker.stop()

    if _shutdown_monitor is not None:
        await _shutdown_monitor.stop()
        _shutdown_monitor = None

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


























def _worker_running(slot: str) -> bool:
    return bool(registry.get_worker(slot).state.running)


























@app.get("/state")
async def get_state(request: Request):
    return registry.build_ui_state()








@app.get("/alerts")
async def fleet_alerts(limit: int = Query(50, ge=1, le=200)):
    from core.observability.alerts import alert_store

    return {"status": "ok", "alerts": alert_store.recent(limit=limit)}








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
    registry.reset_stats_display_counters(account_id)
    fresh_stats = compute_daily_stats(list(ACCOUNTS))
    reset_scope = account_id or "global"
    account_states_patch = {
        slot: registry.get_worker(slot).state.to_dict()
        for slot in reset_slots
    }

    await event_bus.publish(
        EventType.STATS_RESET,
        reset_scope,
        {
            "reset_timestamp": ts,
            "reset_at": get_reset_at_iso(account_id),
            "account_id": account_id,
            "scope": "account" if account_id else "global",
            "daily_stats": fresh_stats,
            "account_states": account_states_patch,
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








@app.get("/health")
async def health():
    return {"status": "ok"}


# ── Groups (API-only writes to master list) ─────────────────────────────────













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




# ── Fleet defaults (global forward link / campaign message) ───────────────────











# ── Message ───────────────────────────────────────────────────────────────────







# ── Account UI helpers ────────────────────────────────────────────────────────







# ── Login (per-slot isolated state) ───────────────────────────────────────────

def _duplicate_phone_login_response(phone: str, slot: str) -> dict | None:
    """Block the same Telegram number on two dashboard slots."""
    hit = find_logged_in_slot_by_phone(phone, exclude_slot=slot)
    if not hit:
        return None
    existing_slot, info = hit
    return {
        "success": False,
        "error": duplicate_phone_login_message(existing_slot, info),
        "existing_slot": existing_slot,
    }








# ── DM Inbox (private chats only — independent of forwarding workers) ─────────























































# ── CRM (lead management on top of inbox) ─────────────────────────────────────



























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












# ── Candidates / Profiles tracker ───────────────────────────────────────────
# Replaces the old "Profiles list update Form" Google Sheet. All CRUD happens
# from the dashboard's Candidates tab and persists to data/candidates.json.









def _viewer_reference(request: Request) -> str | None:
    from core import dashboard_auth_vps as auth
    from core.dashboard_access import operator_profile

    return auth.scoped_reference(operator_profile(request))


def _ops_by(request: Request) -> str:
    from core.dashboard_access import operator_profile

    profile = operator_profile(request)
    return (profile.get("reference") or profile.get("username") or "dashboard").strip()[:120]








































# ── Data room (business opportunities & partners) ─────────────────────────────

def _data_room_admin_only(request: Request) -> bool:
    from core import dashboard_auth_vps as dashboard_auth

    profile = dashboard_auth.operator_profile_from_cookies(dict(request.cookies))
    return dashboard_auth.is_admin_profile(profile)






































# ── Payment proofs ──────────────────────────────────────────────────────────────













# ── Resume versions ───────────────────────────────────────────────────────────

def _resume_file_response(path: str, entry: dict, *, inline: bool = False) -> FileResponse:
    mime = entry.get("mime_type") or "application/octet-stream"
    name = entry.get("original_name") or entry.get("filename") or "resume"
    if inline:
        # For inline viewing, don't set filename (prevents forced download)
        return FileResponse(
            path,
            media_type=mime,
            headers={"Content-Disposition": f'inline; filename="{name}"'},
        )
    return FileResponse(
        path,
        media_type=mime,
        filename=name,
    )


def _resolve_resume_hit(cid: str, rid: str):
    from features import candidate_store

    hit = candidate_store.get_resume(cid, rid)
    if hit is not None:
        return hit
    # File on disk but JSON metadata missing (e.g. after partial restore).
    folder = os.path.join(candidate_store.RESUMES_DIR, cid)
    if not os.path.isdir(folder):
        return None
    for fname in os.listdir(folder):
        if not fname.startswith(rid):
            continue
        path = os.path.join(folder, fname)
        if not os.path.isfile(path):
            continue
        ext = fname.rsplit(".", 1)[-1].lower() if "." in fname else ""
        mime = {
            "pdf": "application/pdf",
            "doc": "application/msword",
            "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            "txt": "text/plain",
        }.get(ext, "application/octet-stream")
        return path, {
            "id": rid,
            "filename": fname,
            "original_name": fname,
            "mime_type": mime,
        }
    return None












# ── Referrer identities and payment accounts ───────────────────────────────────


@app.get("/api/referrers", dependencies=[Depends(_require_fleet_admin)])
@app.get("/referrers", dependencies=[Depends(_require_fleet_admin)])
async def referrers_list():
    from features.referrer_registry import list_payment_accounts, list_referrers

    accounts = list_payment_accounts()
    counts: dict[str, int] = {}
    for account in accounts:
        key = str(account.get("referrer_id") or "")
        counts[key] = counts.get(key, 0) + 1
    return {
        "status": "ok",
        "referrers": [
            {**row, "payment_account_count": counts.get(str(row.get("id") or ""), 0)}
            for row in list_referrers(include_inactive=True)
        ],
    }


@app.get(
    "/api/referrers/{referrer_id}/payment-accounts",
    dependencies=[Depends(_require_fleet_admin)],
)
@app.get(
    "/referrers/{referrer_id}/payment-accounts",
    dependencies=[Depends(_require_fleet_admin)],
)
async def referrer_payment_accounts_list(referrer_id: str):
    from features.referrer_registry import list_payment_accounts, resolve_referrer

    referrer = resolve_referrer(referrer_id)
    if referrer is None:
        raise HTTPException(status_code=404, detail="Referrer not found")
    return {
        "status": "ok",
        "referrer": referrer,
        "accounts": list_payment_accounts(referrer_id=referrer["id"]),
    }


@app.post(
    "/api/referrers/{referrer_id}/payment-accounts",
    dependencies=[Depends(_require_fleet_admin)],
)
@app.post(
    "/referrers/{referrer_id}/payment-accounts",
    dependencies=[Depends(_require_fleet_admin)],
)
async def referrer_payment_account_add(
    request: Request,
    referrer_id: str,
    body: dict = Body(...),
):
    from features.referrer_registry import add_payment_account

    try:
        account = add_payment_account(referrer_id, body, actor=_ops_by(request))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"status": "ok", "account": account}


@app.patch(
    "/api/referrer-payment-accounts/{account_id}",
    dependencies=[Depends(_require_fleet_admin)],
)
@app.patch(
    "/referrer-payment-accounts/{account_id}",
    dependencies=[Depends(_require_fleet_admin)],
)
async def referrer_payment_account_update(
    request: Request,
    account_id: str,
    body: dict = Body(...),
):
    from features.referrer_registry import update_payment_account

    try:
        account = update_payment_account(account_id, body, actor=_ops_by(request))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"status": "ok", "account": account}


@app.delete(
    "/api/referrer-payment-accounts/{account_id}",
    dependencies=[Depends(_require_fleet_admin)],
)
@app.delete(
    "/referrer-payment-accounts/{account_id}",
    dependencies=[Depends(_require_fleet_admin)],
)
async def referrer_payment_account_delete(request: Request, account_id: str):
    from features.referrer_registry import remove_unverified_payment_account

    try:
        removed = remove_unverified_payment_account(
            account_id,
            actor=_ops_by(request),
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if not removed:
        raise HTTPException(status_code=404, detail="Payment account not found")
    return {"status": "ok"}


# ── Handler / reference expenses (legacy route names retained) ────────────────











# ── Handler expense proofs (payment screenshots) ────────────────────────────────







# ── Company expenses (operational costs) ─────────────────────────────────────────











# ── Handler base salaries (hybrid pay model) ────────────────────────────────────
#
# A handler can be on a fixed monthly base salary (this) PLUS their 50%
# commission on every rupee a referred client pays (computed live from
# the candidates table). The hybrid total is what the Handler Payouts
# card and Top Performers chips already show.







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

    @app.get("/oauth-home")
    async def serve_oauth_home():
        return FileResponse(
            os.path.join(STATIC_DIR, "oauth-home.html"),
            media_type="text/html",
            headers=_NO_CACHE,
        )

    @app.get("/privacy")
    async def serve_privacy_policy():
        return FileResponse(
            os.path.join(STATIC_DIR, "privacy.html"),
            media_type="text/html",
            headers=_NO_CACHE,
        )

    @app.get("/terms")
    async def serve_terms_of_service():
        return FileResponse(
            os.path.join(STATIC_DIR, "terms.html"),
            media_type="text/html",
            headers=_NO_CACHE,
        )

    @app.get("/{full_path:path}")
    async def serve_spa(full_path: str):
        # Never serve index.html for API-like paths (avoids JSON parse errors in the UI)
        api_roots = {
            "groups", "account", "accounts", "login", "auth", "message", "start", "stop",
            "state", "health", "ws", "inbox", "crm", "stats", "admin", "ai", "voice",
            "candidates", "data-room", "public", "metrics", "alerts", "push", "analytics",
            "handler-expenses", "handler-salaries", "company-expenses",
            "forward-message", "operator-tasks", "demo-tools", "slot-screenshot", "api",
        }
        first = full_path.split("/")[0] if full_path else ""
        if first in api_roots:
            from fastapi import HTTPException
            raise HTTPException(status_code=404, detail="Not Found")
        file_path = os.path.join(STATIC_DIR, full_path)
        if os.path.exists(file_path):
            return FileResponse(file_path)
        return FileResponse(
            os.path.join(STATIC_DIR, "index.html"),
            headers=_NO_CACHE,
        )


# --- domain routers (extracted; Wave A) ---
from api.routers.accounts import router as accounts_router
app.include_router(accounts_router)
from api.routers.ai import router as ai_router
app.include_router(ai_router)
from api.routers.auth import router as auth_router
app.include_router(auth_router)
from api.routers.candidates import router as candidates_router
app.include_router(candidates_router)
from api.routers.crm import router as crm_router
app.include_router(crm_router)
from api.routers.data_room import router as data_room_router
app.include_router(data_room_router)
from api.routers.expenses import router as expenses_router
app.include_router(expenses_router)
from api.routers.fleet import router as fleet_router
app.include_router(fleet_router)
from api.routers.forwarding import router as forwarding_router
app.include_router(forwarding_router)
from api.routers.groups import router as groups_router
app.include_router(groups_router)
from api.routers.inbox import router as inbox_router
app.include_router(inbox_router)
from api.routers.stats import router as stats_router
app.include_router(stats_router)
