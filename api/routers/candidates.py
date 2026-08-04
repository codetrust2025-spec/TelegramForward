"""Auto-extracted candidates routes (pure move from server.py)."""
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
    _ops_by,
    _resolve_resume_hit,
    _resume_file_response,
    _viewer_reference,
)

router = APIRouter()

@router.get("/candidates")
async def candidates_list(
    request: Request,
    stage: str | None = Query(default=None),
    task: str | None = Query(default=None),
    search: str | None = Query(default=None),
    month: str | None = Query(default=None),
    pending_only: bool = Query(default=False),
    reference: str | None = Query(default=None),
    service_type: str | None = Query(default=None),
    ai_filter: str | None = Query(default=None),
):
    from core.dashboard_access import handler_reference_scope
    from features import candidate_store

    reference = handler_reference_scope(request, reference)
    rows = candidate_store.list_candidates(
        stage=stage, task=task, search=search, month=month,
        pending_only=pending_only, reference=reference, service_type=service_type,
    )
    if ai_filter and os.getenv("AI_INTERVIEW_OFFER_TRACKING_ENABLED", "false").lower() == "true":
        from core.recruitment_mail_store import candidate_filter_ids
        allowed = candidate_filter_ids(ai_filter)
        rows = [row for row in rows if str(row.get("id")) in allowed]
    return {"status": "ok", "candidates": rows, "count": len(rows)}
@router.get("/candidates/stats")
async def candidates_stats(
    request: Request,
    month: str | None = Query(default=None),
    reference: str | None = Query(default=None),
    service_type: str | None = Query(default=None),
):
    from core.dashboard_access import handler_payout_reference_scope
    from features import candidate_store

    # Earnings and payout totals must never expose another handler's figures.
    reference = handler_payout_reference_scope(request, reference)
    return {"status": "ok", "stats": candidate_store.stats(month=month, reference=reference, service_type=service_type)}
@router.get("/candidates/roster")
async def candidates_active_roster(
    request: Request,
    month: str | None = Query(default=None),
    reference: str | None = Query(default=None),
):
    """Active (in_progress) candidates with technology grouping."""
    from core.dashboard_access import handler_reference_scope
    from features import candidate_store

    reference = handler_reference_scope(request, reference)
    roster = candidate_store.active_roster(month=month, reference=reference)
    return {"status": "ok", **roster}
@router.get("/candidates/roster.csv")
async def candidates_active_roster_csv(
    request: Request,
    month: str | None = Query(default=None),
    reference: str | None = Query(default=None),
):
    """Download active candidates as CSV (name, tech, contact, payment, etc.)."""
    from fastapi.responses import Response

    from core.dashboard_access import handler_reference_scope
    from features import candidate_store

    reference = handler_reference_scope(request, reference)
    roster = candidate_store.active_roster(month=month, reference=reference)
    csv_text = candidate_store.roster_csv_rows(roster.get("candidates") or [])
    filename = "active_candidates.csv"
    if month and month != "all":
        filename = f"active_candidates_{month}.csv"
    return Response(
        content="\ufeff" + csv_text,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
@router.get("/candidates/bootstrap")
async def candidates_bootstrap(
    request: Request,
    stage: str | None = Query(default=None),
    task: str | None = Query(default=None),
    search: str | None = Query(default=None),
    month: str | None = Query(default=None),
    pending_only: bool = Query(default=False),
    reference: str | None = Query(default=None),
    include_global_stats: bool = Query(default=False),
):
    from core.dashboard_access import handler_reference_scope
    from features import candidate_store

    reference = handler_reference_scope(request, reference)
    payload = candidate_store.bootstrap_data(
        stage=stage,
        task=task,
        search=search,
        month=month,
        pending_only=pending_only,
        reference=reference,
        include_global_stats=include_global_stats,
    )
    return {"status": "ok", **payload}
@router.get("/candidates/pending-works")
async def candidates_pending_works(
    request: Request,
    response: Response,
    month: str | None = Query(default=None),
    reference: str | None = Query(default=None),
):
    from core.dashboard_access import handler_reference_scope
    from features import candidate_store

    reference = handler_reference_scope(request, reference)
    payload = candidate_store.pending_works(month=month, reference=reference)
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    response.headers["Pragma"] = "no-cache"
    return {"status": "ok", **payload}
@router.get("/candidates/interviews/daily")
async def candidates_interviews_daily(
    request: Request,
    date: str | None = Query(default=None),
    attendee: str | None = Query(default=None),
    search: str | None = Query(default=None),
    channel: str | None = Query(default=None),
    round: str | None = Query(default=None),
    technology: str | None = Query(default=None),
):
    from fastapi import HTTPException

    from features import candidate_store

    day = (date or "").strip()[:10]
    if len(day) != 10:
        raise HTTPException(status_code=400, detail="date must be YYYY-MM-DD")
    viewer = _viewer_reference(request)
    try:
        payload = candidate_store.daily_interview_roster(
            day,
            viewer_reference=viewer,
            filter_attendee=attendee,
            filter_search=search,
            filter_channel=channel,
            filter_round=round,
            filter_technology=technology,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"status": "ok", **payload}
@router.get("/candidates/interviews/monitor")
async def candidates_interviews_monitor(
    request: Request,
    from_date: str | None = Query(default=None, alias="from"),
    to_date: str | None = Query(default=None, alias="to"),
    attendee: str | None = Query(default=None),
    search: str | None = Query(default=None),
    channel: str | None = Query(default=None),
    round: str | None = Query(default=None),
    technology: str | None = Query(default=None),
    upcoming_only: bool = Query(default=False),
):
    from fastapi import HTTPException

    from features import candidate_store

    start = (from_date or "").strip()[:10]
    end = (to_date or "").strip()[:10]
    if len(start) != 10 or len(end) != 10:
        raise HTTPException(status_code=400, detail="from and to must be YYYY-MM-DD")
    viewer = _viewer_reference(request)
    try:
        payload = candidate_store.interview_monitor(
            start,
            end,
            viewer_reference=viewer,
            filter_attendee=attendee,
            filter_search=search,
            filter_channel=channel,
            filter_round=round,
            filter_technology=technology,
            upcoming_only=upcoming_only,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"status": "ok", **payload}
@router.get("/candidates/interviews/upcoming")
async def candidates_interviews_upcoming(
    request: Request,
    days: int = Query(default=14),
    search: str | None = Query(default=None),
    attendee: str | None = Query(default=None),
    channel: str | None = Query(default=None),
    include_today: bool = Query(default=True),
    phase: str | None = Query(default=None),
    lookback_days: int = Query(default=30),
):
    from features import candidate_store

    viewer = _viewer_reference(request)
    payload = candidate_store.interview_upcoming(
        days=days,
        filter_search=search,
        filter_attendee=attendee,
        filter_channel=channel,
        viewer_reference=viewer,
        include_today_pending=include_today,
        phase=phase,
        lookback_days=lookback_days,
    )
    return {"status": "ok", **payload}
@router.get("/candidates/interviews/global")
async def candidates_interviews_global(
    request: Request,
    from_date: str | None = Query(default=None, alias="from"),
    to_date: str | None = Query(default=None, alias="to"),
    attendee: str | None = Query(default=None),
    search: str | None = Query(default=None),
    channel: str | None = Query(default=None),
    round: str | None = Query(default=None),
    technology: str | None = Query(default=None),
    upcoming_only: bool = Query(default=False),
):
    from fastapi import HTTPException

    from features import candidate_store

    start = (from_date or "").strip()[:10]
    end = (to_date or "").strip()[:10]
    if len(start) != 10 or len(end) != 10:
        raise HTTPException(status_code=400, detail="from and to must be YYYY-MM-DD")
    viewer = _viewer_reference(request)
    try:
        payload = candidate_store.interview_global_summary(
            start,
            end,
            viewer_reference=viewer,
            filter_attendee=attendee,
            filter_search=search,
            filter_channel=channel,
            filter_round=round,
            filter_technology=technology,
            upcoming_only=upcoming_only,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"status": "ok", **payload}
@router.get("/candidates/interviews/filter-options")
async def candidates_interviews_filter_options(
    request: Request,
    from_date: str | None = Query(default=None, alias="from"),
    to_date: str | None = Query(default=None, alias="to"),
    channel: str | None = Query(default=None),
    attendee: str | None = Query(default=None),
):
    from features import candidate_store

    viewer = _viewer_reference(request)
    options = candidate_store.interview_candidate_filter_options(
        from_date=from_date,
        to_date=to_date,
        channel=channel,
        viewer_reference=viewer,
        filter_attendee=attendee,
    )
    return {"status": "ok", "options": options}
@router.post("/candidates/interviews/slots")
async def candidates_interviews_slots_create(request: Request, body: dict):
    from core.dashboard_access import assert_candidate_row_access
    from features import candidate_store

    b = body or {}
    candidate_id = (b.get("candidate_id") or "").strip()
    date = (b.get("date") or "").strip()
    time = (b.get("time") or "").strip()
    time_end = (b.get("time_end") or "").strip()
    notes = (b.get("notes") or "").strip()
    interview_round = (b.get("interview_round") or "").strip()
    try:
        if not candidate_id:
            raise ValueError("Select an existing candidate before booking an interview slot")
        existing = candidate_store.get_candidate(candidate_id)
        if not existing:
            raise ValueError("Candidate not found")
        assert_candidate_row_access(request, existing)
        row = candidate_store.assign_interview_slot(
            candidate_id=candidate_id,
            date=date,
            time=time,
            time_end=time_end,
            notes=notes,
            interview_round=interview_round,
        )
    except ValueError as exc:
        return {"status": "error", "message": str(exc)}
    return {"status": "ok", "candidate": row}
@router.patch("/candidates/interviews/slots/{cid}")
async def candidates_interviews_slots_update(cid: str, request: Request, body: dict):
    from core.dashboard_access import assert_candidate_row_access
    from features import candidate_store

    existing = candidate_store.get_candidate(cid)
    if not existing:
        return {"status": "error", "message": "Candidate not found"}
    assert_candidate_row_access(request, existing)
    b = body or {}
    target_id = (b.get("candidate_id") or cid).strip() or cid
    try:
        row = candidate_store.update_interview_slot(
            candidate_id=target_id,
            date=b.get("date") or "",
            time=b.get("time") or "",
            time_end=b.get("time_end") or "",
            notes=b.get("notes") or "",
            interview_round=b.get("interview_round") or "",
            technology=b.get("technology"),
        )
    except ValueError as exc:
        return {"status": "error", "message": str(exc)}
    return {"status": "ok", "candidate": row}
@router.delete("/candidates/interviews/slots/{cid}")
async def candidates_interviews_slots_delete(cid: str, request: Request):
    from core.dashboard_access import assert_candidate_row_access
    from features import candidate_store

    existing = candidate_store.get_candidate(cid)
    if not existing:
        return {"status": "error", "message": "Candidate not found"}
    assert_candidate_row_access(request, existing)
    try:
        row = candidate_store.cancel_interview_slot(candidate_id=cid)
    except ValueError as exc:
        return {"status": "error", "message": str(exc)}
    return {"status": "ok", "candidate": row}
@router.post("/candidates/{cid}/slot-screenshot")
async def candidates_slot_screenshot(cid: str, request: Request):
    from fastapi import HTTPException, UploadFile

    from core.dashboard_access import assert_candidate_row_access
    from features import candidate_store

    existing = candidate_store.get_candidate(cid)
    if not existing:
        raise HTTPException(status_code=404, detail="Candidate not found")
    assert_candidate_row_access(request, existing)
    form = await request.form()
    attachment_type = form.get("attachment_type")
    try:
        from features.candidate_attachments import AttachmentType, parse_attachment_type
        if parse_attachment_type(attachment_type) != AttachmentType.SLOT_SCREENSHOT_PROOF:
            raise ValueError("slot-screenshot requires attachment_type=slot_screenshot_proof")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    upload = form.get("file")
    if upload is None or not isinstance(upload, UploadFile):
        raise HTTPException(status_code=400, detail="file is required")
    data = await upload.read()
    if not data:
        raise HTTPException(status_code=400, detail="Empty file")
    entry = candidate_store.attach_public_slot_screenshot(
        cid,
        data=data,
        original_name=upload.filename or "slot-screenshot.jpg",
        mime_type=upload.content_type or "image/jpeg",
        source="dashboard-upload",
    )
    if not entry:
        raise HTTPException(status_code=400, detail="Screenshot upload failed")
    row = candidate_store.get_candidate(cid) or existing
    return {"status": "ok", "proof": entry, "candidate": row}
@router.post("/candidates/{cid}/interview-attendance")
async def candidates_interview_attendance(cid: str, request: Request, body: dict):
    from core.dashboard_access import assert_candidate_row_access, operator_profile
    from features import candidate_store

    existing = candidate_store.get_candidate(cid)
    if not existing:
        return {"status": "error", "message": "Candidate not found"}
    assert_candidate_row_access(request, existing)
    b = body or {}
    profile = operator_profile(request)
    role = (profile.get("role") or "").strip().lower()
    allow_future = role in {"admin", "handler"}
    requested_status = candidate_store.normalise_interview_attendance_status(
        b.get("status") or "",
        legacy_attended=b.get("attended"),
    )
    if (
        requested_status == candidate_store.RE_SERVICE_STATUS
        and not candidate_store.re_service_grant_allowed(role)
    ):
        return {
            "status": "error",
            "message": "Only an administrator can grant Re-Service.",
        }
    try:
        row = candidate_store.set_interview_attendance(
            cid,
            status=b.get("status") or "",
            remark=b.get("remark") or "",
            attended=b.get("attended"),
            attendee=b.get("attendee"),
            feedback=b.get("feedback"),
            by=_ops_by(request),
            allow_future=allow_future,
        )
    except ValueError as exc:
        return {"status": "error", "message": str(exc)}
    if not row:
        return {"status": "error", "message": "Candidate not found"}
    return {"status": "ok", "candidate": row}
@router.patch("/candidates/{cid}/interview-attendee")
async def candidates_interview_attendee(cid: str, request: Request, body: dict):
    """Change the assigned interview attendee without changing attendance."""
    from fastapi import HTTPException
    from core.dashboard_access import assert_candidate_row_access
    from core.dashboard_access import operator_profile
    from features import candidate_store

    if (operator_profile(request).get("role") or "").strip().lower() != "admin":
        raise HTTPException(status_code=403, detail="Only an admin can reassign an interview attendee")

    existing = candidate_store.get_candidate(cid)
    if not existing:
        return {"status": "error", "message": "Candidate not found"}
    assert_candidate_row_access(request, existing)
    try:
        row = candidate_store.set_interview_attendee(
            cid,
            attendee=(body or {}).get("attendee") or "",
            by=_ops_by(request),
        )
    except ValueError as exc:
        return {"status": "error", "message": str(exc)}
    if not row:
        return {"status": "error", "message": "Candidate not found"}
    return {"status": "ok", "candidate": row}
@router.get("/candidates/{cid}")
async def candidates_get(cid: str, request: Request):
    from core.dashboard_access import assert_candidate_row_access
    from features import candidate_store

    row = candidate_store.get_candidate_detail(cid)
    if not row:
        return {"status": "error", "message": "Candidate not found"}
    assert_candidate_row_access(request, row)
    return {"status": "ok", "candidate": row}
@router.post("/candidates")
async def candidates_create(request: Request, body: dict):
    from core.dashboard_access import prepare_candidate_body
    from features import candidate_store

    body = prepare_candidate_body(request, body)
    if not (body.get("name") or "").strip():
        return {"status": "error", "message": "Name is required"}
    try:
        body["ctc_percentage"] = candidate_store.validate_profile_ctc_percentage(body)
        row = candidate_store.create_candidate(body)
    except ValueError as exc:
        return {"status": "error", "message": str(exc), "duplicate_candidate": "already exists" in str(exc).lower()}
    return {"status": "ok", "candidate": row}
@router.patch("/candidates/{cid}")
async def candidates_update(cid: str, request: Request, body: dict):
    from core.dashboard_access import assert_candidate_row_access, prepare_candidate_body
    from features import candidate_store

    existing = candidate_store.get_candidate(cid)
    if not existing:
        return {"status": "error", "message": "Candidate not found"}
    assert_candidate_row_access(request, existing)
    try:
        prepared = prepare_candidate_body(request, body or {})
        prepared["ctc_percentage"] = candidate_store.validate_profile_ctc_percentage(
            prepared,
            existing=existing,
        )
        row = candidate_store.update_candidate(cid, prepared)
    except ValueError as exc:
        return {"status": "error", "message": str(exc), "duplicate_phone": "already belongs" in str(exc).lower()}
    if not row:
        return {"status": "error", "message": "Candidate not found"}
    return {"status": "ok", "candidate": row}
@router.delete("/candidates/{cid}")
async def candidates_delete(cid: str, request: Request):
    from core.dashboard_access import assert_candidate_row_access
    from features import candidate_store

    existing = candidate_store.get_candidate(cid)
    if not existing:
        return {"status": "error", "message": "Candidate not found"}
    assert_candidate_row_access(request, existing)
    ok = candidate_store.delete_candidate(cid)
    if not ok:
        return {"status": "error", "message": "Candidate not found"}
    return {"status": "ok"}
@router.post("/candidates/{cid}/proofs")
async def candidates_upload_proof(
    request: Request,
    cid: str,
    file: UploadFile = File(...),
    note: str = Form(default=""),
    attachment_type: str = Form(default=""),
):
    """Attach a payment screenshot (image) to a candidate.

    Multipart form fields:
      - `file`  (required): the screenshot itself.
      - `note`  (optional): a short caption (e.g. "₹10k UPI · 26 May").
    """
    from core.dashboard_access import assert_candidate_row_access
    from features import candidate_store
    from features.candidate_attachments import AttachmentType, parse_attachment_type
    from fastapi import HTTPException

    try:
        if parse_attachment_type(attachment_type) != AttachmentType.PAYMENT_PROOF:
            raise ValueError("Payment upload requires attachment_type=payment_proof")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    existing = candidate_store.get_candidate(cid)
    if not existing:
        return {"status": "error", "message": "Candidate not found"}
    assert_candidate_row_access(request, existing)
    ai_extraction = None
    fraud_check = None
    try:
        raw = await file.read()
        try:
            from features.payment_verification_engine import verify_payment_screenshot
            expected = candidate_store.effective_expected_payment(existing)
            paid = int(existing.get("payment") or 0)
            ai_extraction = await asyncio.to_thread(
                verify_payment_screenshot,
                raw,
                file.content_type or "image/jpeg",
                source_module="candidate_payment_proof",
                expected_amount=max(0, expected - paid),
                entity_id=cid,
                entity_name=existing.get("name") or "",
                candidate_id=cid,
                referrer_id=existing.get("reference") or "",
                referrer_hint=existing.get("reference") or "",
                purpose="candidate_payment",
                payment_scope=(
                    "ROUND"
                    if existing.get("service_type") == "round_wise"
                    else "PROFILE"
                ),
            )
        except Exception as exc:
            logger.exception("Central payment verification failed for candidate proof")
            return {
                "status": "error",
                "message": f"Payment screenshot could not be verified: {exc}",
            }
        from features.payment_fraud_detection import assess_payment_proof
        fraud_check = assess_payment_proof(raw, ai_extraction, candidate_id=cid, candidate_name=existing.get("name") or "")
        if fraud_check["decision"] == "rejected":
            match = (fraud_check.get("duplicate_matches") or [{}])[0]
            return {"status": "error", "message": " ".join(fraud_check["reasons"]), "fraud_check": fraud_check, "duplicate_candidate": match.get("candidate_name")}
        metadata = {
            "sha256": fraud_check["sha256"], "utr_number": fraud_check.get("utr_number") or "",
            "transaction_id": (ai_extraction or {}).get("transaction_id") or "",
            "payment_status": (ai_extraction or {}).get("status") or "",
            "company_payment_verified": bool((ai_extraction or {}).get("company_payment_verified")),
            "booking_eligible": bool((ai_extraction or {}).get("booking_eligible")),
            "verification_state": (ai_extraction or {}).get("verification_state") or "",
            "receiver_name": (ai_extraction or {}).get("receiver_name") or "",
            "receiver_upi_id": (ai_extraction or {}).get("receiver_upi_id") or "",
            "receiver_phone": (ai_extraction or {}).get("receiver_phone") or "",
            "verified_amount": int((ai_extraction or {}).get("amount") or 0),
            "receiver_account": (ai_extraction or {}).get("receiver_account") or "",
            "receiver_type": (ai_extraction or {}).get("receiver_type") or "unknown",
            "ledger_entry_id": (ai_extraction or {}).get("ledger_entry_id") or "",
            "ledger_action": (ai_extraction or {}).get("ledger_action") or "",
            "ledger_status": (ai_extraction or {}).get("ledger_status") or "",
            "payment_id": (ai_extraction or {}).get("payment_id") or "",
            "evidence_id": (ai_extraction or {}).get("evidence_id") or "",
            "entitlement_id": (ai_extraction or {}).get("entitlement_id") or "",
            "payment_scope": (ai_extraction or {}).get("payment_scope") or "",
            "source_module": "candidate_payment_proof",
            "fraud_decision": fraud_check["decision"], "fraud_reasons": fraud_check["reasons"],
            "fraud_warnings": fraud_check["warnings"], "fraud_checked_at": fraud_check["checked_at"],
        }
        entry = candidate_store.add_payment_proof(
            cid,
            data=raw,
            original_name=file.filename or "",
            mime_type=file.content_type or "",
            note=note or "",
            metadata=metadata,
        )
    except ValueError as e:
        return {"status": "error", "message": str(e)}
    if entry is None:
        return {"status": "error", "message": "Candidate not found"}
    row = candidate_store.get_candidate(cid)
    # Keep the interactive request deterministic. Calling Ollama here used to
    # hold the browser in "Uploading" for up to 30 minutes.
    if ai_extraction:
        amount = int(ai_extraction.get("amount") or 0)
        status = str(ai_extraction.get("status") or "unknown")
        ai_extraction["narrative"] = (
            f"Ollama detected a payment of ₹{amount:,} with status {status}."
            if amount
            else "Payment proof saved; extracted details require manual review."
        )
    resp = {"status": "ok", "proof": entry, "candidate": row}
    if ai_extraction:
        resp["ai_extraction"] = ai_extraction
    if fraud_check:
        resp["fraud_check"] = fraud_check
    return resp
@router.get("/candidates/{cid}/proofs/{pid}")
async def candidates_serve_proof(cid: str, pid: str, request: Request):
    from core.dashboard_access import assert_candidate_row_access
    from features import candidate_store

    existing = candidate_store.get_candidate(cid)
    if not existing:
        return {"status": "error", "message": "Proof not found"}
    assert_candidate_row_access(request, existing)
    hit = candidate_store.get_proof(cid, pid)
    if hit is None:
        return {"status": "error", "message": "Proof not found"}
    path, entry = hit
    return FileResponse(
        path,
        media_type=entry.get("mime_type") or "application/octet-stream",
        filename=entry.get("original_name") or entry.get("filename"),
    )
@router.get("/candidates/{cid}/attachments/{attachment_type}/{attachment_id}")
async def candidates_serve_typed_attachment(
    cid: str, attachment_type: str, attachment_id: str, request: Request
):
    from fastapi import HTTPException
    from core.dashboard_access import assert_candidate_row_access
    from features import candidate_store

    existing = candidate_store.get_candidate(cid)
    if not existing:
        raise HTTPException(status_code=404, detail="Attachment not found")
    assert_candidate_row_access(request, existing)
    try:
        hit = candidate_store.get_attachment(cid, attachment_id, attachment_type)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    if hit is None:
        raise HTTPException(status_code=404, detail="Attachment not found")
    path, entry = hit
    return FileResponse(
        path,
        media_type=entry.get("mime_type") or "application/octet-stream",
        filename=entry.get("original_name") or entry.get("filename"),
    )
@router.post("/candidates/{cid}/profile-photo")
async def candidates_upload_profile_photo(
    request: Request,
    cid: str,
    file: UploadFile = File(...),
    attachment_type: str = Form(default=""),
):
    from core.dashboard_access import assert_candidate_row_access
    from features import candidate_store
    from features.candidate_attachments import AttachmentType, parse_attachment_type
    from fastapi import HTTPException

    existing = candidate_store.get_candidate(cid)
    if not existing:
        return {"status": "error", "message": "Candidate not found"}
    assert_candidate_row_access(request, existing)
    try:
        if parse_attachment_type(attachment_type) != AttachmentType.PROFILE_PHOTO:
            raise ValueError("Profile photo upload requires attachment_type=profile_photo")
        entry = candidate_store.set_profile_photo(
            cid,
            data=await file.read(),
            original_name=file.filename or "",
            mime_type=file.content_type or "",
            note="Candidate profile photo",
            metadata={"source_module": "candidate_profile"},
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return {
        "status": "ok",
        "profile_photo": entry,
        "candidate": candidate_store.get_candidate(cid),
    }
@router.delete("/candidates/{cid}/proofs/{pid}")
async def candidates_delete_proof(cid: str, pid: str, request: Request):
    from core.dashboard_access import assert_candidate_row_access
    from features import candidate_store

    existing = candidate_store.get_candidate(cid)
    if not existing:
        return {"status": "error", "message": "Proof not found"}
    assert_candidate_row_access(request, existing)
    ok = candidate_store.delete_proof(cid, pid)
    if not ok:
        return {"status": "error", "message": "Proof not found"}
    row = candidate_store.get_candidate(cid)
    return {"status": "ok", "candidate": row}
@router.patch("/candidates/{cid}/proofs/{pid}")
async def candidates_update_proof_note(cid: str, pid: str, body: dict, request: Request):
    from core.dashboard_access import assert_candidate_row_access
    from features import candidate_store

    existing = candidate_store.get_candidate(cid)
    if not existing:
        return {"status": "error", "message": "Proof not found"}
    assert_candidate_row_access(request, existing)
    note = (body or {}).get("note", "")
    entry = candidate_store.update_proof_note(cid, pid, note)
    if entry is None:
        return {"status": "error", "message": "Proof not found"}
    return {"status": "ok", "proof": entry}
@router.post("/candidates/{cid}/resumes")
async def candidates_upload_resume(
    request: Request,
    cid: str,
    file: UploadFile = File(...),
    note: str = Form(default=""),
):
    from core.dashboard_access import assert_candidate_row_access
    from features import candidate_store

    existing = candidate_store.get_candidate(cid)
    if not existing:
        return {"status": "error", "message": "Candidate not found"}
    assert_candidate_row_access(request, existing)
    raw = await file.read()
    mime = file.content_type or ""

    # Classify before storing. Running this afterwards meant a document that
    # is plainly not a resume - an offer letter for a different person - was
    # filed as one and stayed there: the verdict was computed, then only
    # attached to the response.
    ai_extraction = None
    try:
        if "pdf" in mime.lower():
            from features.ollama_resume_extract import extract_resume_with_ollama
            ai_extraction = await asyncio.to_thread(extract_resume_with_ollama, raw, mime)
    except Exception:
        # An unavailable model must never block a genuine resume, so a
        # question that could not be asked counts as no objection.
        ai_extraction = None
    if ai_extraction is not None and ai_extraction.get("is_resume") is False:
        return {
            "status": "error",
            "message": (
                "This file does not look like a resume, so it was not saved. "
                "Upload the candidate's resume instead."
            ),
            "ai_extraction": ai_extraction,
        }

    try:
        entry = candidate_store.add_resume(
            cid,
            data=raw,
            original_name=file.filename or "",
            mime_type=mime,
            note=note or "",
        )
    except ValueError as e:
        return {"status": "error", "message": str(e)}
    if entry is None:
        return {"status": "error", "message": "Candidate not found"}
    row = candidate_store.get_candidate(cid)
    resp = {"status": "ok", "resume": entry, "candidate": row}
    if ai_extraction and ai_extraction.get("is_resume"):
        resp["ai_extraction"] = ai_extraction
    return resp
@router.get("/candidates/{cid}/resumes/{rid}")
async def candidates_serve_resume(cid: str, rid: str, request: Request):
    from core.dashboard_access import assert_candidate_row_access
    from features import candidate_store

    existing = candidate_store.get_candidate(cid)
    if existing:
        assert_candidate_row_access(request, existing)
    hit = _resolve_resume_hit(cid, rid)
    if hit is None:
        return {"status": "error", "message": "Resume not found"}
    path, entry = hit
    return _resume_file_response(path, entry, inline=False)
@router.get("/candidates/{cid}/resumes/{rid}/preview")
async def candidates_serve_resume_preview(cid: str, rid: str, request: Request):
    from core.dashboard_access import assert_candidate_row_access
    from features import candidate_store

    existing = candidate_store.get_candidate(cid)
    if existing:
        assert_candidate_row_access(request, existing)
    hit = _resolve_resume_hit(cid, rid)
    if hit is None:
        raise HTTPException(status_code=404, detail="Resume not found")
    path, entry = hit
    return _resume_file_response(path, entry, inline=True)
@router.delete("/candidates/{cid}/resumes/{rid}")
async def candidates_delete_resume(cid: str, rid: str, request: Request):
    from core.dashboard_access import assert_candidate_row_access
    from features import candidate_store

    existing = candidate_store.get_candidate(cid)
    if not existing:
        return {"status": "error", "message": "Resume not found"}
    assert_candidate_row_access(request, existing)
    ok = candidate_store.delete_resume(cid, rid)
    if not ok:
        return {"status": "error", "message": "Resume not found"}
    row = candidate_store.get_candidate(cid)
    return {"status": "ok", "candidate": row}
@router.patch("/candidates/{cid}/resumes/{rid}")
async def candidates_update_resume_note(cid: str, rid: str, body: dict, request: Request):
    from core.dashboard_access import assert_candidate_row_access
    from features import candidate_store

    existing = candidate_store.get_candidate(cid)
    if not existing:
        return {"status": "error", "message": "Resume not found"}
    assert_candidate_row_access(request, existing)
    note = (body or {}).get("note", "")
    entry = candidate_store.update_resume_note(cid, rid, note)
    if entry is None:
        return {"status": "error", "message": "Resume not found"}
    return {"status": "ok", "resume": entry}
