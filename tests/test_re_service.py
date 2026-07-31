"""Re-Service: one admin-granted free repeat interview.

The grant must waive payment for exactly one booking, stay invisible to the
candidate flow, and never leak into the statuses the roster already uses.
"""
from __future__ import annotations

import pytest

from features import candidate_store as cs


@pytest.fixture
def store(monkeypatch, tmp_path):
    monkeypatch.setattr(cs, "_FILE", str(tmp_path / "candidates.json"), raising=False)
    monkeypatch.setattr(cs, "_CACHE", None, raising=False)
    try:
        cs._save({"candidates": []})
    except Exception:
        pytest.skip("candidate store not file-backed in this build")
    return cs


def _mk(store, **over):
    row = store.create_candidate({
        "name": over.pop("name", "Re Service Tester"),
        "phone": over.pop("phone", "9876500011"),
        "service_type": "round_wise",
        "interview_round": over.pop("interview_round", "L1"),
        "technology": "Testing",
        **over,
    })
    return row


def test_re_service_is_a_valid_status_but_not_attendance(store):
    assert "re_service" in cs.INTERVIEW_ATTENDANCE_STATUSES
    assert cs.normalise_interview_attendance_status("re_service") == "re_service"
    # The four pre-existing statuses keep their exact meaning.
    for legacy in ("attended", "not_attended", "cancelled", "rescheduled"):
        assert cs.normalise_interview_attendance_status(legacy) == legacy


def test_marking_re_service_grants_eligibility(store):
    row = _mk(store)
    assert cs.candidate_is_re_service_eligible(name=row["name"], phone=row["phone"]) is False

    cs.set_interview_attendance(row["id"], status="re_service", by="admin")

    assert cs.candidate_is_re_service_eligible(name=row["name"], phone=row["phone"]) is True
    saved = cs.get_candidate(row["id"])
    # It must not masquerade as a completed interview.
    assert saved["interview_attended"] is False


def test_eligible_candidate_skips_the_payment_gate(store):
    row = _mk(store, phone="9876500022")
    blocked = cs.slot_booking_payment_block_reason(
        row["name"], require_payment_proof=True, phone=row["phone"], interview_round="L1"
    )
    assert blocked  # normal round-wise booking still demands a receipt

    cs.set_interview_attendance(row["id"], status="re_service", by="admin")

    assert cs.slot_booking_payment_block_reason(
        row["name"], require_payment_proof=True, phone=row["phone"], interview_round="L1"
    ) is None


def test_grant_is_found_by_phone_and_round(store):
    row = _mk(store, name="Lookup Probe", phone="9876500033", interview_round="L2")
    cs.set_interview_attendance(row["id"], status="re_service", by="admin")

    assert cs.find_re_service_grant(phone="9876500033", interview_round="L2") is not None
    assert cs.find_re_service_grant(candidate_id=row["id"]) is not None
    assert cs.find_re_service_grant(name="Lookup Probe") is not None
    assert cs.find_re_service_grant(phone="9000000000", name="Someone Else") is None


def test_completed_re_service_interview_burns_the_grant(store):
    row = _mk(store, name="Burn Once", phone="9876500044")
    cs.set_interview_attendance(row["id"], status="re_service", by="admin")
    assert cs.candidate_is_re_service_eligible(phone="9876500044") is True

    # Booking marks the row as a re-service booking...
    cs.update_candidate(
        row["id"],
        {"re_service_booking": True, "re_service_grant_row_id": row["id"]},
        allow_slot_without_rules=True,
    )
    # ...and completing it removes the benefit.
    cs.set_interview_attendance(
        row["id"], status="attended", remark="done", feedback="positive",
        by="admin", allow_future=True,
    )

    assert cs.candidate_is_re_service_eligible(phone="9876500044") is False
    assert cs.slot_booking_payment_block_reason(
        row["name"], require_payment_proof=True, phone="9876500044"
    )


def test_full_lifecycle_free_once_then_charged_again(store):
    row = _mk(store, name="Free Repeat", phone="9876500077")

    with pytest.raises(cs.PaymentDueError):
        cs.import_confirmed_interview_slot(
            name="Free Repeat", date="2026-08-05", time="10:00", interview_round="L1",
            technology="Testing", phone="9876500077", service_type="round_wise",
        )

    cs.set_interview_attendance(row["id"], status="re_service", by="admin")

    booked, _action = cs.import_confirmed_interview_slot(
        name="Free Repeat", date="2026-08-05", time="10:00", interview_round="L1",
        technology="Testing", phone="9876500077", service_type="round_wise",
    )
    # The marker must survive the write, or the benefit could never be burned.
    assert booked["re_service_booking"] is True
    assert booked["re_service_grant_row_id"]

    cs.set_interview_attendance(
        booked["id"], status="attended", remark="done", feedback="positive",
        by="admin", allow_future=True,
    )

    assert cs.candidate_is_re_service_eligible(phone="9876500077") is False
    with pytest.raises(cs.PaymentDueError):
        cs.import_confirmed_interview_slot(
            name="Free Repeat", date="2026-08-12", time="11:00", interview_round="L2",
            technology="Testing", phone="9876500077", service_type="round_wise",
        )


def test_normal_candidates_are_completely_unaffected(store):
    row = _mk(store, name="Regular Person", phone="9876500055")
    assert cs.find_re_service_grant(phone="9876500055") is None
    assert cs.candidate_is_re_service_eligible(phone="9876500055") is False
    # Attendance still behaves exactly as before for an ordinary round.
    cs.set_interview_attendance(
        row["id"], status="attended", remark="ok", feedback="negative",
        by="admin", allow_future=True,
    )
    saved = cs.get_candidate(row["id"])
    assert saved["interview_attendance_status"] == "attended"
    assert saved["interview_attended"] is True
    assert saved.get("re_service_eligible") in (False, None, "")
