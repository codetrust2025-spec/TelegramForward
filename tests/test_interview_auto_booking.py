from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

from services import interview_auto_booking as booking


def result(classification="interview_confirmed", confidence=.96, **interview):
    details = {
        "date": "2026-07-20", "time": "03:00 PM", "timezone": "Asia/Kolkata",
        "round": "L1", "mode": "Online", "meeting_link": "https://meet.test/room",
        "location": None,
    }
    details.update(interview)
    return {
        "classification": classification, "classification_source": "OLLAMA",
        "ai_validation_status": "VALIDATED", "confidence": confidence,
        "requires_manual_review": False, "interview": details,
        "candidate": {"email": "candidate@test.invalid"},
        "company": {"name": "Example"}, "job": {"title": "Engineer"},
        "summary": "Confirmed interview", "reason": "Explicit schedule",
    }


@pytest.mark.parametrize(("raw", "expected"), [
    ("12:00 AM", "00:00"), ("12:00 PM", "12:00"), ("1:05 AM", "01:05"),
    ("01:05 PM", "13:05"), ("11:59 PM", "23:59"),
])
def test_12_hour_times_are_normalized(raw, expected):
    assert booking.parse_interview_time(raw) == expected


@pytest.mark.parametrize("raw", ["", "15:00", "13:00 PM", "3 PM", "00:30 AM", "03:60 PM"])
def test_invalid_interview_times_are_blocked(raw):
    with pytest.raises(booking.BookingValidationError, match="12-hour"):
        booking.parse_interview_time(raw)


@pytest.mark.parametrize(("raw", "key"), [("IST", "Asia/Kolkata"), ("Asia/Kolkata", "Asia/Kolkata"), ("America/New_York", "America/New_York")])
def test_supported_timezones_are_explicit(raw, key):
    assert booking.validate_timezone(raw).key == key


@pytest.mark.parametrize("raw", ["", "India/Imaginary", "GMT+5:30"])
def test_invalid_timezones_are_blocked(raw):
    with pytest.raises(booking.BookingValidationError):
        booking.validate_timezone(raw)


def test_non_ist_schedule_is_converted_to_booking_calendar():
    value = result(date="2026-07-20", time="03:00 PM", timezone="America/New_York")
    schedule = booking.normalized_schedule(value, now=datetime(2026, 7, 15, tzinfo=ZoneInfo("America/New_York")))
    assert schedule == {"date": "2026-07-21", "time": "00:30", "time_end": "01:00", "source_timezone": "America/New_York"}


def test_past_schedule_is_blocked():
    value = result(date="2026-07-14")
    with pytest.raises(booking.BookingValidationError, match="future"):
        booking.normalized_schedule(value, now=datetime(2026, 7, 15, tzinfo=ZoneInfo("Asia/Kolkata")))


@pytest.mark.parametrize(("confidence", "manual", "date_value", "allowed"), [
    (.95, False, "2026-07-20", True), (.85, False, "2026-07-20", True),
    (.79, False, "2026-07-20", False), (.95, True, "2026-07-20", False),
    (.85, False, "", False),
])
def test_confidence_and_completeness_gate(monkeypatch, confidence, manual, date_value, allowed):
    monkeypatch.setenv("AI_INTERVIEW_AUTO_BOOKING_ENABLED", "true")
    value = result(confidence=confidence, date=date_value)
    value["requires_manual_review"] = manual
    if allowed:
        booking.validate_ai_for_booking(value, "interview_confirmed")
    else:
        with pytest.raises(booking.BookingValidationError):
            booking.validate_ai_for_booking(value, "interview_confirmed")


@pytest.mark.parametrize(("source", "validation"), [("FALLBACK", "VALIDATED"), ("OLLAMA", "UNAVAILABLE"), ("FAILURE_REVIEW", "UNAVAILABLE")])
def test_only_validated_ollama_can_mutate_slots(monkeypatch, source, validation):
    monkeypatch.setenv("AI_INTERVIEW_AUTO_BOOKING_ENABLED", "true")
    value = result(); value["classification_source"] = source; value["ai_validation_status"] = validation
    with pytest.raises(booking.BookingValidationError, match="validated Ollama"):
        booking.validate_ai_for_booking(value, "interview_confirmed")


def install_store_fakes(monkeypatch, *, rows=None, payment_reason=None, conflicts=None):
    candidate = {"id": "c1", "name": "Rahul", "reference": "Owner", "payment": 10000, "expected_payment": 20000, "service_type": "profile_service"}
    monkeypatch.setattr(booking.mail_store, "record_interview_analysis", lambda **kwargs: {"id": "ia1"})
    monkeypatch.setattr(booking.mail_store, "booking_audit_for_message", lambda *args, **kwargs: None)
    audits = []
    monkeypatch.setattr(booking.mail_store, "record_booking_audit", lambda **kwargs: audits.append(kwargs) or {"id": "audit1", **kwargs})
    monkeypatch.setattr(booking.mail_store, "attach_booking_to_notification", lambda *args, **kwargs: {"id": "n1", **kwargs})
    monkeypatch.setattr(booking.candidate_store, "get_candidate", lambda _cid: candidate)
    monkeypatch.setattr(booking.candidate_store, "candidate_identity_ids", lambda _cid: ["c1"])
    monkeypatch.setattr(booking.candidate_store, "list_candidates", lambda **kwargs: list(rows or []))
    monkeypatch.setattr(booking.candidate_store, "slot_confirm_block_reason", lambda _row: payment_reason)
    monkeypatch.setattr(booking.candidate_store, "find_interview_slot_conflicts", lambda *args, **kwargs: list(conflicts or []))
    return candidate, audits


def execute(value):
    return booking.execute_auto_booking(
        mailbox={"id": "mb1", "candidate_id": "c1", "email_address": "candidate@test.invalid"},
        message={"provider_message_id": "gm1", "provider_thread_id": "gt1"},
        event={"mailbox_message_id": "mm1", "notification": {"id": "n1", "email_analysis_id": "ma1"}},
        result=value, correlation_id="corr1",
    )


def test_valid_confirmed_interview_books_without_approval(monkeypatch):
    monkeypatch.setenv("AI_INTERVIEW_AUTO_BOOKING_ENABLED", "true")
    _candidate, audits = install_store_fakes(monkeypatch)
    monkeypatch.setattr(booking.candidate_store, "assign_interview_slot", lambda **kwargs: {"id": "slot1", **kwargs})
    outcome = execute(result())
    assert outcome["status"] == "Auto Booked"
    assert outcome["booking"]["time"] == "15:00"
    assert audits[-1]["auto_booked"] is True


def test_payment_failure_creates_blocked_audit_without_booking(monkeypatch):
    monkeypatch.setenv("AI_INTERVIEW_AUTO_BOOKING_ENABLED", "true")
    _candidate, audits = install_store_fakes(monkeypatch, payment_reason="Record at least payment received")
    monkeypatch.setattr(booking.candidate_store, "assign_interview_slot", lambda **kwargs: pytest.fail("must not book"))
    outcome = execute(result())
    assert outcome["failure_code"] == "PAYMENT_VALIDATION_FAILED"
    assert audits[-1]["payment_status"] == "BLOCKED"


def test_duplicate_booking_is_blocked(monkeypatch):
    monkeypatch.setenv("AI_INTERVIEW_AUTO_BOOKING_ENABLED", "true")
    row = {"id": "c1", "name": "Rahul", "slot_confirmed": True, "date": "2026-07-20", "time": "15:00"}
    install_store_fakes(monkeypatch, rows=[row])
    outcome = execute(result())
    assert outcome["failure_code"] == "DUPLICATE_BOOKING"


def test_slot_overlap_is_blocked(monkeypatch):
    monkeypatch.setenv("AI_INTERVIEW_AUTO_BOOKING_ENABLED", "true")
    install_store_fakes(monkeypatch, conflicts=[{"id": "other", "name": "Other"}])
    outcome = execute(result())
    assert outcome["failure_code"] == "SLOT_CONFLICT"


def test_candidate_email_mismatch_is_blocked(monkeypatch):
    monkeypatch.setenv("AI_INTERVIEW_AUTO_BOOKING_ENABLED", "true")
    install_store_fakes(monkeypatch)
    value = result(); value["candidate"]["email"] = "someone-else@test.invalid"
    assert execute(value)["failure_code"] == "CANDIDATE_MAPPING_FAILED"


def test_reschedule_updates_existing_booking_and_preserves_previous(monkeypatch):
    monkeypatch.setenv("AI_INTERVIEW_AUTO_BOOKING_ENABLED", "true")
    old = {"id": "slot1", "name": "Rahul", "slot_confirmed": True, "date": "2026-07-19", "time": "14:00"}
    _candidate, audits = install_store_fakes(monkeypatch, rows=[old])
    monkeypatch.setattr(booking.candidate_store, "reschedule_confirmed_interview_slot_by_name", lambda *args, **kwargs: ({"id": "slot1", "date": kwargs["date"], "time": kwargs["time"]}, "rescheduled"))
    outcome = execute(result("interview_rescheduled"))
    assert outcome["status"] == "Rescheduled"
    assert audits[-1]["previous_booking"]["date"] == "2026-07-19"


def test_cancellation_keeps_audit_and_does_not_touch_payment(monkeypatch):
    monkeypatch.setenv("AI_INTERVIEW_AUTO_BOOKING_ENABLED", "true")
    old = {"id": "slot1", "name": "Rahul", "slot_confirmed": True, "date": "2026-07-19", "time": "14:00"}
    _candidate, audits = install_store_fakes(monkeypatch, rows=[old], payment_reason="must not be evaluated")
    monkeypatch.setattr(booking.candidate_store, "cancel_confirmed_interview_slot_by_name", lambda *args, **kwargs: ({"id": "slot1", "slot_confirmed": False}, "cancelled"))
    outcome = execute(result("interview_cancelled", date=None, time=None, timezone=None))
    assert outcome["status"] == "Cancelled"
    assert audits[-1]["payment_status"] == "NOT_REQUIRED"


def test_duplicate_gmail_message_does_not_mutate_booking_twice(monkeypatch):
    monkeypatch.setenv("AI_INTERVIEW_AUTO_BOOKING_ENABLED", "true")
    install_store_fakes(monkeypatch)
    monkeypatch.setattr(booking.mail_store, "booking_audit_for_message", lambda *args: {"id": "audit1", "auto_booked": True, "booking_id": "slot1", "booking_status": "Auto Booked"})
    monkeypatch.setattr(booking.candidate_store, "assign_interview_slot", lambda **kwargs: pytest.fail("must not book twice"))
    outcome = execute(result())
    assert outcome["duplicate"] is True
