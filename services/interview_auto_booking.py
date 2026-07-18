"""Validated Ollama interview outcomes applied through the existing slot store."""
from __future__ import annotations

import logging
import os
import re
import uuid
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Any
from threading import Lock
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from core import recruitment_mail_store as mail_store
from features import candidate_store

logger = logging.getLogger("teleautomation.interview_auto_booking")

ACTIONABLE = {"interview_confirmed", "interview_rescheduled", "interview_cancelled"}
TIME_RE = re.compile(r"^(0?[1-9]|1[0-2]):([0-5]\d)\s*([AP]M)$", re.I)
_BOOKING_LOCK = Lock()


@dataclass
class BookingValidationError(ValueError):
    code: str
    message: str
    payment_status: str = "NOT_CHECKED"
    duplicate_status: str = "NOT_CHECKED"
    conflict_status: str = "NOT_CHECKED"

    def __str__(self) -> str:
        return self.message


def _threshold(name: str, default: float) -> float:
    raw = float(os.getenv(name, str(default)))
    return max(0.0, min(1.0, raw / 100 if raw > 1 else raw))


def _confidence(result: dict[str, Any]) -> float:
    value = float(result.get("confidence") or 0)
    return value / 100 if value > 1 else value


def parse_interview_time(value: str) -> str:
    """Require the AI contract's 12-hour clock and return candidate-store HH:MM."""
    match = TIME_RE.fullmatch(str(value or "").strip())
    if not match:
        raise BookingValidationError("INVALID_TIME", "Interview time must use 12-hour HH:MM AM/PM format.")
    hour, minute, meridiem = int(match.group(1)), int(match.group(2)), match.group(3).upper()
    if meridiem == "AM" and hour == 12:
        hour = 0
    elif meridiem == "PM" and hour != 12:
        hour += 12
    return f"{hour:02d}:{minute:02d}"


def validate_timezone(value: str) -> ZoneInfo:
    name = str(value or "").strip()
    if name.upper() == "IST":
        name = "Asia/Kolkata"
    if not name:
        raise BookingValidationError("MISSING_TIMEZONE", "Interview timezone is required for automatic booking.")
    try:
        return ZoneInfo(name)
    except ZoneInfoNotFoundError as exc:
        raise BookingValidationError("INVALID_TIMEZONE", "Interview timezone is not a valid IANA timezone.") from exc


def normalized_schedule(result: dict[str, Any], *, now: datetime | None = None) -> dict[str, str]:
    interview = result.get("interview") or {}
    try:
        day = date.fromisoformat(str(interview.get("date") or ""))
    except ValueError as exc:
        raise BookingValidationError("INVALID_DATE", "Interview date is missing or is not ISO YYYY-MM-DD.") from exc
    source_time = parse_interview_time(str(interview.get("time") or ""))
    source_zone = validate_timezone(str(interview.get("timezone") or ""))
    source_dt = datetime.combine(day, datetime.strptime(source_time, "%H:%M").time(), source_zone)
    current = now or datetime.now(source_zone)
    if current.tzinfo is None:
        current = current.replace(tzinfo=source_zone)
    if source_dt <= current.astimezone(source_zone):
        raise BookingValidationError("PAST_INTERVIEW", "Interview date and time must be in the future.")
    local = source_dt.astimezone(ZoneInfo("Asia/Kolkata"))
    end = local + timedelta(minutes=max(15, int(os.getenv("AI_INTERVIEW_DEFAULT_DURATION_MINUTES", "30"))))
    return {
        "date": local.date().isoformat(), "time": local.strftime("%H:%M"),
        "time_end": end.strftime("%H:%M"), "source_timezone": source_zone.key,
    }


def validate_ai_for_booking(result: dict[str, Any], classification: str) -> None:
    if os.getenv("AI_INTERVIEW_AUTO_BOOKING_ENABLED", "false").lower() != "true":
        raise BookingValidationError("AUTO_BOOKING_DISABLED", "Automatic interview booking is disabled by configuration.")
    if result.get("classification_source") != "OLLAMA" or result.get("ai_validation_status") != "VALIDATED":
        raise BookingValidationError("AI_NOT_VALIDATED", "A validated Ollama analysis is required for automatic booking.")
    confidence = _confidence(result)
    review = _threshold("AI_INTERVIEW_REVIEW_THRESHOLD", 0.80)
    automatic = _threshold("AI_INTERVIEW_AUTO_BOOK_THRESHOLD", 0.90)
    if confidence < review:
        raise BookingValidationError("LOW_CONFIDENCE", "AI confidence is below the review threshold.")
    interview = result.get("interview") or {}
    required = all(str(interview.get(key) or "").strip() for key in ("date", "time", "timezone"))
    if confidence < automatic and not required:
        raise BookingValidationError("MEDIUM_CONFIDENCE_INCOMPLETE", "Medium-confidence booking requires explicit date, time, and timezone.")
    if bool(result.get("requires_manual_review")):
        raise BookingValidationError("AI_REQUIRES_REVIEW", "Ollama marked this interview for manual review.")
    if classification not in ACTIONABLE:
        raise BookingValidationError("NOT_ACTIONABLE", "This interview classification does not change a booking.")


def _payment_check(candidate: dict[str, Any], schedule: dict[str, str] | None) -> None:
    preview = dict(candidate)
    preview["slots_group_posted"] = True
    if schedule:
        preview["date"] = schedule["date"]
    reason = candidate_store.slot_confirm_block_reason(preview)
    if reason:
        raise BookingValidationError("PAYMENT_VALIDATION_FAILED", reason, payment_status="BLOCKED")


def _candidate_slots(candidate: dict[str, Any]) -> list[dict[str, Any]]:
    identity_ids = set(candidate_store.candidate_identity_ids(str(candidate["id"])))
    name = str(candidate.get("name") or "").strip().casefold()
    return [
        row for row in candidate_store.list_candidates(stage="all", month="all")
        if str(row.get("id")) in identity_ids or str(row.get("name") or "").strip().casefold() == name
    ]


def _confirmed_slots(candidate: dict[str, Any]) -> list[dict[str, Any]]:
    return [row for row in _candidate_slots(candidate) if row.get("slot_confirmed") and row.get("date")]


def _same_text(left: Any, right: Any) -> bool:
    return bool(str(left or "").strip()) and str(left or "").strip().casefold() == str(right or "").strip().casefold()


def _reference_schedule(result: dict[str, Any], classification: str) -> dict[str, str] | None:
    """Normalize an explicitly stated old/cancelled schedule without requiring it to be future."""
    interview = result.get("interview") or {}
    prefix = "original_" if classification == "interview_rescheduled" else ""
    day = str(interview.get(f"{prefix}date") or "").strip()
    raw_time = str(interview.get(f"{prefix}time") or "").strip()
    timezone_name = str(interview.get(f"{prefix}timezone") or "").strip()
    if not (day and raw_time and timezone_name):
        return None
    try:
        source_day = date.fromisoformat(day)
        source_time = parse_interview_time(raw_time)
        source_zone = validate_timezone(timezone_name)
    except (ValueError, BookingValidationError):
        return None
    source_dt = datetime.combine(source_day, datetime.strptime(source_time, "%H:%M").time(), source_zone)
    local = source_dt.astimezone(ZoneInfo("Asia/Kolkata"))
    return {"date": local.date().isoformat(), "time": local.strftime("%H:%M")}


def _resolve_existing_slot(
    slots: list[dict[str, Any]], *, result: dict[str, Any], message: dict[str, Any], classification: str,
) -> dict[str, Any]:
    """Resolve one slot using stable interview identity; never pick an arbitrary recent row."""
    if not slots:
        raise BookingValidationError("BOOKING_NOT_FOUND", "No active interview booking was found.")
    if len(slots) == 1:
        return slots[0]
    interview = result.get("interview") or {}
    company = (result.get("company") or {}).get("name")
    role = (result.get("job") or {}).get("title")
    round_name = interview.get("round")
    thread_id = message.get("provider_thread_id")
    reference = _reference_schedule(result, classification)
    ranked: list[tuple[int, dict[str, Any]]] = []
    for row in slots:
        score = 0
        if thread_id and _same_text(row.get("interview_source_thread_id"), thread_id):
            score += 100
        if reference and str(row.get("date") or "")[:10] == reference["date"] and str(row.get("time") or "")[:5] == reference["time"]:
            score += 80
        if round_name and _same_text(candidate_store.normalise_interview_round(row.get("interview_round")), candidate_store.normalise_interview_round(round_name)):
            score += 30
        if company and _same_text(row.get("interview_company"), company):
            score += 20
        if role and _same_text(row.get("interview_role"), role):
            score += 15
        ranked.append((score, row))
    ranked.sort(key=lambda item: item[0], reverse=True)
    if ranked[0][0] <= 0 or (len(ranked) > 1 and ranked[0][0] == ranked[1][0]):
        raise BookingValidationError(
            "BOOKING_AMBIGUOUS",
            "Multiple active interview slots match this candidate; the source email does not identify one safely.",
        )
    return ranked[0][1]


def _booking_metadata(result: dict[str, Any], message: dict[str, Any], schedule: dict[str, str] | None) -> dict[str, str]:
    return {
        "interview_company": str((result.get("company") or {}).get("name") or ""),
        "interview_role": str((result.get("job") or {}).get("title") or ""),
        "interview_source_thread_id": str(message.get("provider_thread_id") or ""),
        "interview_source_message_id": str(message.get("provider_message_id") or ""),
        "interview_source_timezone": str((schedule or {}).get("source_timezone") or ""),
    }


def execute_auto_booking(
    *, mailbox: dict[str, Any], message: dict[str, Any], event: dict[str, Any],
    result: dict[str, Any], correlation_id: str | None = None,
) -> dict[str, Any]:
    """Serialize validation plus mutation so concurrent mailbox jobs cannot race."""
    with _BOOKING_LOCK:
        with mail_store.candidate_booking_lock(str(mailbox.get("candidate_id") or "")):
            return _execute_auto_booking(
                mailbox=mailbox, message=message, event=event, result=result,
                correlation_id=correlation_id,
            )


def _execute_auto_booking(
    *, mailbox: dict[str, Any], message: dict[str, Any], event: dict[str, Any],
    result: dict[str, Any], correlation_id: str | None = None,
) -> dict[str, Any]:
    """Apply one actionable classification and durably describe every outcome."""
    correlation_id = correlation_id or str(uuid.uuid4())
    classification = mail_store.canonical_classification(result)
    notification = event.get("notification") or {}
    analysis = mail_store.record_interview_analysis(
        mailbox_message_id=event["mailbox_message_id"],
        email_analysis_id=notification.get("email_analysis_id"), mailbox_id=mailbox["id"],
        gmail_message_id=message["provider_message_id"],
        gmail_thread_id=message.get("provider_thread_id"), candidate_id=mailbox["candidate_id"],
        result=result, validation_status=str(result.get("ai_validation_status") or "UNAVAILABLE"),
        processing_status="VALIDATING",
    )
    existing_audit = mail_store.booking_audit_for_message(message["provider_message_id"], classification)
    if existing_audit and existing_audit.get("auto_booked"):
        logger.info("Duplicate Gmail interview outcome ignored correlation_id=%s gmail_message_id=%s", correlation_id, message["provider_message_id"])
        return {"status": existing_audit.get("booking_status") or "Already Processed", "event_type": "notification_created",
                "booking": {"id": existing_audit.get("booking_id")}, "audit": existing_audit,
                "notification": notification, "duplicate": True}
    booking: dict[str, Any] | None = None
    previous: dict[str, Any] | None = None
    payment_status, duplicate_status, conflict_status = "NOT_CHECKED", "NOT_CHECKED", "NOT_CHECKED"
    try:
        validate_ai_for_booking(result, classification)
        candidate = candidate_store.get_candidate(str(mailbox.get("candidate_id") or ""))
        if not candidate:
            raise BookingValidationError("CANDIDATE_MAPPING_FAILED", "The connected mailbox candidate could not be found.")
        result_email = str((result.get("candidate") or {}).get("email") or "").strip().lower()
        mailbox_email = str(mailbox.get("email_address") or "").strip().lower()
        if result_email and mailbox_email and result_email != mailbox_email:
            raise BookingValidationError("CANDIDATE_MAPPING_FAILED", "The AI candidate email does not match the authorized mailbox.")
        schedule = None if classification == "interview_cancelled" else normalized_schedule(result)
        if classification != "interview_cancelled":
            _payment_check(candidate, schedule); payment_status = "PASSED"
        slots = _confirmed_slots(candidate)
        if classification == "interview_confirmed":
            duplicate = next((row for row in slots if str(row.get("date"))[:10] == schedule["date"] and str(row.get("time"))[:5] == schedule["time"]), None)
            if duplicate:
                raise BookingValidationError("DUPLICATE_BOOKING", "This candidate already has the same interview booking.", payment_status="PASSED", duplicate_status="DUPLICATE")
            duplicate_status = "PASSED"
            conflicts = candidate_store.find_interview_slot_conflicts(schedule["date"], schedule["time"], schedule["time_end"])
            if conflicts:
                raise BookingValidationError("SLOT_CONFLICT", "The interview overlaps an existing confirmed slot.", payment_status="PASSED", duplicate_status="PASSED", conflict_status="CONFLICT")
            conflict_status = "PASSED"
            booking = candidate_store.assign_interview_slot(
                candidate_id=str(candidate["id"]), date=schedule["date"], time=schedule["time"],
                time_end=schedule["time_end"], interview_round=str((result.get("interview") or {}).get("round") or ""),
                notes="Automatically booked from validated interview email (AI Mail Monitoring).",
                **_booking_metadata(result, message, schedule),
            )
            booking_status, event_type = "Auto Booked", "slot_auto_booked"
        elif classification == "interview_rescheduled":
            target = _resolve_existing_slot(slots, result=result, message=message, classification=classification)
            conflicts = candidate_store.find_interview_slot_conflicts(
                schedule["date"], schedule["time"], schedule["time_end"], exclude_candidate_id=str(target["id"]),
            )
            if conflicts:
                raise BookingValidationError("SLOT_CONFLICT", "The rescheduled interview overlaps an existing confirmed slot.", payment_status="PASSED", conflict_status="CONFLICT")
            previous = dict(target)
            booking = candidate_store.update_interview_slot(
                candidate_id=str(target["id"]), date=schedule["date"], time=schedule["time"],
                time_end=schedule["time_end"], interview_round=str((result.get("interview") or {}).get("round") or ""),
                notes="Rescheduled from validated interview email (AI Mail Monitoring).",
                **_booking_metadata(result, message, schedule),
            )
            duplicate_status, conflict_status = "PASSED", "PASSED"
            booking_status, event_type = "Rescheduled", "interview_rescheduled"
        else:
            target = _resolve_existing_slot(slots, result=result, message=message, classification=classification)
            previous = dict(target)
            booking = candidate_store.cancel_interview_slot(candidate_id=str(target["id"]))
            payment_status, duplicate_status, conflict_status = "NOT_REQUIRED", "PASSED", "NOT_REQUIRED"
            booking_status, event_type = "Cancelled", "interview_cancelled"
        audit = mail_store.record_booking_audit(
            analysis_id=analysis["id"], candidate_id=str(candidate["id"]),
            gmail_message_id=message["provider_message_id"], gmail_thread_id=message.get("provider_thread_id"),
            classification=classification, booking_id=str(booking.get("id") or ""), auto_booked=True,
            validation_status="PASSED", payment_status=payment_status, duplicate_status=duplicate_status,
            conflict_status=conflict_status, booking_status=booking_status,
            previous_booking=previous, new_booking=booking, correlation_id=correlation_id,
        )
        updated_notification = mail_store.attach_booking_to_notification(
            notification.get("id"), audit_id=audit["id"], booking_id=str(booking.get("id") or ""),
            booking_status=booking_status, result=result, priority="high",
            display_status="Interview Automatically Booked" if booking_status == "Auto Booked" else f"Interview {booking_status}",
        ) if notification.get("id") else {}
        logger.info("Interview booking applied correlation_id=%s classification=%s booking_id=%s", correlation_id, classification, booking.get("id"))
        return {"status": booking_status, "event_type": event_type, "booking": booking, "audit": audit, "notification": updated_notification}
    except BookingValidationError as exc:
        payment_status = exc.payment_status if exc.payment_status != "NOT_CHECKED" else payment_status
        duplicate_status = exc.duplicate_status if exc.duplicate_status != "NOT_CHECKED" else duplicate_status
        conflict_status = exc.conflict_status if exc.conflict_status != "NOT_CHECKED" else conflict_status
        audit = mail_store.record_booking_audit(
            analysis_id=analysis["id"], candidate_id=str(mailbox.get("candidate_id") or ""),
            gmail_message_id=message["provider_message_id"], gmail_thread_id=message.get("provider_thread_id"),
            classification=classification, booking_id=None, auto_booked=False,
            validation_status="BLOCKED", payment_status=payment_status, duplicate_status=duplicate_status,
            conflict_status=conflict_status, booking_status="Blocked", failure_code=exc.code,
            failure_message=exc.message, correlation_id=correlation_id,
        )
        updated_notification = mail_store.attach_booking_to_notification(
            notification.get("id"), audit_id=audit["id"], booking_id=None,
            booking_status="Blocked", result=result, priority="review_required",
            display_status="Automatic Booking Blocked", detail=exc.message,
        ) if notification.get("id") else {}
        logger.info("Interview booking blocked correlation_id=%s code=%s", correlation_id, exc.code)
        return {"status": "Blocked", "event_type": "slot_booking_blocked", "failure_code": exc.code, "message": exc.message, "audit": audit, "notification": updated_notification}
    except Exception as exc:
        code = type(exc).__name__
        audit = mail_store.record_booking_audit(
            analysis_id=analysis["id"], candidate_id=str(mailbox.get("candidate_id") or ""),
            gmail_message_id=message["provider_message_id"], gmail_thread_id=message.get("provider_thread_id"),
            classification=classification, booking_id=None, auto_booked=False,
            validation_status="FAILED", payment_status=payment_status, duplicate_status=duplicate_status,
            conflict_status=conflict_status, booking_status="Processing Failed", failure_code=code,
            failure_message="Automatic booking could not be completed safely.", correlation_id=correlation_id,
        )
        updated_notification = mail_store.attach_booking_to_notification(
            notification.get("id"), audit_id=audit["id"], booking_id=None,
            booking_status="Processing Failed", result=result, priority="review_required",
            display_status="Automatic Booking Processing Failed",
            detail="Review the mail analysis and retry after the underlying error is resolved.",
        ) if notification.get("id") else {}
        logger.exception("Interview booking processing failed correlation_id=%s code=%s", correlation_id, code)
        return {"status": "Processing Failed", "event_type": "slot_booking_blocked", "failure_code": code,
                "message": "Automatic booking could not be completed safely.", "audit": audit,
                "notification": updated_notification}
