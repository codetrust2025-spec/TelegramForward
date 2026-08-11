from __future__ import annotations

import copy
from contextlib import contextmanager
from pathlib import Path

import pytest

from core import recruitment_mail_store as mail_store
from services import interview_reconciliation as reconciliation


REPO = Path(__file__).resolve().parents[1]


class _Cursor:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        return False


class _TransactionalConnection:
    """Small transaction double which restores all writes on an exception."""

    def __init__(self, state):
        self.state = state
        self.before = None

    def __enter__(self):
        self.before = copy.deepcopy(self.state)
        return self

    def __exit__(self, exc_type, exc, traceback):
        if exc_type is not None:
            self.state.clear()
            self.state.update(self.before)
        return False

    def cursor(self):
        return _Cursor()


def _base_state():
    booking = {
        "id": "booking-1",
        "name": "Candidate Example",
        "date": "2026-08-20",
        "time": "17:30",
        "time_end": "18:00",
        "interview_round": "L1",
        "slot_confirmed": True,
        "interview_booking_source": "candidate_booked",
        "interview_company": "",
        "unprotected_note": "must also remain untouched",
    }
    return {
        "message": {
            "id": "message-1",
            "provider_message_id": "gmail-message-1",
            "provider_thread_id": "gmail-thread-1",
            "mailbox_id": "mailbox-1",
            "candidate_id": "message-candidate-1",
            "processing_status": "AI_RETRY_PENDING",
            "ai_retry_after": "later",
            "ai_lease_expires_at": "lease",
        },
        "booking": booking,
        "failed_analysis": {
            "id": "failed-analysis-1",
            "mailbox_message_id": "message-1",
            "status": "FAILED",
            "error_code": "SCHEMA_VALIDATION_FAILED",
            "structured_result": {"raw_response_hash": "evidence-hash"},
        },
        "relationship": None,
        "audits": [],
    }


def _arguments(state, **overrides):
    values = {
        "mailbox_message_id": "message-1",
        "gmail_message_id": "gmail-message-1",
        "booking_id": "booking-1",
        "expected_candidate_name": "Candidate Example",
        "expected_date": "2026-08-20",
        "expected_time": "5:30 PM",
        "expected_time_end": "6:00 PM",
        "expected_round": "L1",
        "expected_booking_hash": reconciliation.booking_protected_hash(
            state["booking"]
        ),
        "company_name": "Example Company",
        "reconciled_by": "operator@example.invalid",
    }
    values.update(overrides)
    return values


def _install_transaction_doubles(monkeypatch, state):
    locked = []

    monkeypatch.setattr(
        reconciliation,
        "_preliminary_candidate_id",
        lambda message_id, gmail_id: state["message"]["candidate_id"],
    )
    @contextmanager
    def candidate_lock(candidate_id):
        locked.append(candidate_id)
        yield

    monkeypatch.setattr(
        reconciliation.mail_store, "candidate_booking_lock", candidate_lock
    )
    monkeypatch.setattr(
        reconciliation,
        "get_connection",
        lambda: _TransactionalConnection(state),
    )
    monkeypatch.setattr(
        reconciliation,
        "_lock_message",
        lambda cur, message_id, gmail_id: copy.deepcopy(state["message"]),
    )
    monkeypatch.setattr(
        reconciliation,
        "_lock_booking",
        lambda cur, booking_id: copy.deepcopy(state["booking"]),
    )
    monkeypatch.setattr(
        reconciliation,
        "_canonical_identity",
        lambda cur, candidate_id: (
            "other-canonical-candidate"
            if candidate_id == "different-booking-candidate"
            else "canonical-candidate-1"
        ),
    )
    monkeypatch.setattr(
        reconciliation,
        "_failed_analysis",
        lambda cur, message_id: (
            copy.deepcopy(state["failed_analysis"]),
            reconciliation._analysis_fingerprint(state["failed_analysis"]),
        ),
    )
    monkeypatch.setattr(
        reconciliation,
        "_relationship_for_message",
        lambda cur, message_id: copy.deepcopy(state["relationship"]),
    )
    monkeypatch.setattr(
        reconciliation,
        "_audit_exists",
        lambda cur, relationship_id: any(
            row["source_id"] == relationship_id for row in state["audits"]
        ),
    )

    def upsert(cur, **fields):
        relationship = state["relationship"] or {
            "id": fields["relationship_id"],
            "mailbox_message_id": state["message"]["id"],
        }
        relationship.update(
            {
                "reconciled_booking_id": fields["booking_id"],
                "reconciliation_status": reconciliation.RECONCILIATION_STATUS,
                "reconciled_by": fields["reconciled_by"],
                "structured_result": {
                    "reconciliation": {
                        "company": {"name": fields["company_name"]},
                        "booking_hash": fields["booking_hash"],
                    }
                },
            }
        )
        state["relationship"] = relationship
        return copy.deepcopy(relationship)

    monkeypatch.setattr(reconciliation, "_upsert_relationship", upsert)

    def terminalize(cur, message):
        previous = state["message"]["processing_status"]
        state["message"].update(
            {
                "processing_status": reconciliation.TERMINAL_MESSAGE_STATUS,
                "previous_processing_status": previous,
                "ai_retry_after": None,
                "ai_lease_expires_at": None,
            }
        )
        return copy.deepcopy(state["message"])

    monkeypatch.setattr(reconciliation, "_terminalize_message", terminalize)

    def write_audit(cur, **fields):
        audit_id = f"audit-{len(state['audits']) + 1}"
        state["audits"].append(
            {
                "id": audit_id,
                "action": "INTERVIEW_MESSAGE_RECONCILED",
                "source_id": fields["relationship_id"],
                "booking_hash": fields["booking_hash"],
            }
        )
        return audit_id

    monkeypatch.setattr(reconciliation, "_write_audit", write_audit)
    return locked


def test_reconciliation_is_atomic_terminal_and_preserves_booking_and_failed_analysis(
    monkeypatch,
):
    state = _base_state()
    before_booking = copy.deepcopy(state["booking"])
    before_analysis = copy.deepcopy(state["failed_analysis"])
    locked = _install_transaction_doubles(monkeypatch, state)

    result = reconciliation.reconcile_interview_message_to_booking(
        **_arguments(state)
    )

    assert result["created"] is True
    assert result["booking_hash_before"] == result["booking_hash_after"]
    assert state["booking"] == before_booking
    assert state["failed_analysis"] == before_analysis
    assert state["message"]["processing_status"] == "INTERVIEW_RECONCILED"
    assert state["message"]["ai_retry_after"] is None
    assert state["message"]["ai_lease_expires_at"] is None
    assert state["relationship"]["reconciled_booking_id"] == "booking-1"
    assert state["relationship"]["structured_result"]["reconciliation"][
        "company"
    ] == {"name": "Example Company"}
    assert len(state["audits"]) == 1
    assert state["audits"][0]["action"] == "INTERVIEW_MESSAGE_RECONCILED"
    assert locked == ["message-candidate-1"]


def test_same_message_and_booking_reconciliation_is_idempotent(monkeypatch):
    state = _base_state()
    _install_transaction_doubles(monkeypatch, state)

    first = reconciliation.reconcile_interview_message_to_booking(
        **_arguments(state)
    )
    second = reconciliation.reconcile_interview_message_to_booking(
        **_arguments(state)
    )

    assert first["created"] is True
    assert second["created"] is False
    assert second["relationship_id"] == first["relationship_id"]
    assert len(state["audits"]) == 1
    assert state["relationship"]["reconciled_booking_id"] == "booking-1"


@pytest.mark.parametrize(
    ("override", "code"),
    [
        ({"expected_candidate_name": "Different Candidate"}, "CANDIDATE_MISMATCH"),
        ({"expected_date": "2026-08-21"}, "SCHEDULE_MISMATCH"),
        ({"expected_time": "4:30 PM"}, "SCHEDULE_MISMATCH"),
        ({"expected_time_end": "6:30 PM"}, "SCHEDULE_MISMATCH"),
        ({"expected_round": "L2"}, "ROUND_MISMATCH"),
        ({"expected_booking_hash": "0" * 64}, "BOOKING_HASH_MISMATCH"),
    ],
)
def test_mismatched_booking_evidence_is_rejected_without_writes(
    monkeypatch, override, code
):
    state = _base_state()
    before = copy.deepcopy(state)
    _install_transaction_doubles(monkeypatch, state)

    with pytest.raises(reconciliation.InterviewReconciliationError) as caught:
        reconciliation.reconcile_interview_message_to_booking(
            **_arguments(state, **override)
        )

    assert caught.value.code == code
    assert state == before


def test_message_and_booking_candidate_identity_mismatch_is_rejected(monkeypatch):
    state = _base_state()
    state["booking"]["id"] = "different-booking-candidate"
    before = copy.deepcopy(state)
    _install_transaction_doubles(monkeypatch, state)

    with pytest.raises(reconciliation.InterviewReconciliationError) as caught:
        reconciliation.reconcile_interview_message_to_booking(
            **_arguments(
                state,
                expected_booking_hash=reconciliation.booking_protected_hash(
                    state["booking"]
                ),
            )
        )

    assert caught.value.code == "CANDIDATE_MISMATCH"
    assert state == before


def test_candidate_change_between_preflight_and_row_lock_is_rejected(monkeypatch):
    state = _base_state()
    state["message"]["candidate_id"] = "changed-candidate"
    before = copy.deepcopy(state)
    _install_transaction_doubles(monkeypatch, state)
    monkeypatch.setattr(
        reconciliation,
        "_preliminary_candidate_id",
        lambda message_id, gmail_id: "message-candidate-1",
    )

    with pytest.raises(reconciliation.InterviewReconciliationError) as caught:
        reconciliation.reconcile_interview_message_to_booking(
            **_arguments(state)
        )

    assert caught.value.code == "MESSAGE_CANDIDATE_CHANGED"
    assert state == before


def test_conflicting_second_booking_reconciliation_is_rejected(monkeypatch):
    state = _base_state()
    state["relationship"] = {
        "id": "relationship-1",
        "mailbox_message_id": "message-1",
        "reconciled_booking_id": "different-booking",
    }
    before = copy.deepcopy(state)
    _install_transaction_doubles(monkeypatch, state)

    with pytest.raises(reconciliation.InterviewReconciliationError) as caught:
        reconciliation.reconcile_interview_message_to_booking(
            **_arguments(state)
        )

    assert caught.value.code == "RECONCILIATION_CONFLICT"
    assert state == before


@pytest.mark.parametrize(
    ("helper", "code"),
    [("_lock_message", "MESSAGE_NOT_FOUND"), ("_lock_booking", "BOOKING_NOT_FOUND")],
)
def test_missing_exact_record_is_rejected(monkeypatch, helper, code):
    state = _base_state()
    before = copy.deepcopy(state)
    _install_transaction_doubles(monkeypatch, state)

    def missing(*args, **kwargs):
        raise reconciliation.InterviewReconciliationError(code, "missing")

    monkeypatch.setattr(reconciliation, helper, missing)
    with pytest.raises(reconciliation.InterviewReconciliationError) as caught:
        reconciliation.reconcile_interview_message_to_booking(
            **_arguments(state)
        )

    assert caught.value.code == code
    assert state == before


def test_failed_final_immutability_invariant_rolls_back_every_write(monkeypatch):
    state = _base_state()
    before = copy.deepcopy(state)
    _install_transaction_doubles(monkeypatch, state)
    original_terminalize = reconciliation._terminalize_message

    def corrupt_then_terminalize(cur, message):
        terminal = original_terminalize(cur, message)
        state["booking"]["time"] = "10:00"
        return terminal

    monkeypatch.setattr(reconciliation, "_terminalize_message", corrupt_then_terminalize)

    with pytest.raises(reconciliation.InterviewReconciliationError) as caught:
        reconciliation.reconcile_interview_message_to_booking(
            **_arguments(state)
        )

    assert caught.value.code == "BOOKING_IMMUTABILITY_FAILED"
    assert state == before


def test_claim_query_cannot_select_reconciled_messages(monkeypatch):
    statements = []

    class Cursor(_Cursor):
        description = []

        def execute(self, sql, params=None):
            statements.append(" ".join(sql.split()))

        def fetchall(self):
            return []

    class Connection:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, traceback):
            return False

        def cursor(self):
            return Cursor()

    monkeypatch.setattr(mail_store, "get_connection", lambda: Connection())

    assert mail_store.claim_ai_messages() == []
    claim = next(sql for sql in statements if "SELECT id FROM mailbox_messages" in sql)
    assert "processing_status IN ('AI_QUEUED','AI_RETRY_PENDING')" in claim
    assert reconciliation.TERMINAL_MESSAGE_STATUS not in claim


def test_migration_is_additive_idempotent_and_enforces_canonical_relationship():
    sql = (
        REPO
        / "core"
        / "migrations"
        / "024_recruitment_mail_interview_reconciliation.sql"
    ).read_text(encoding="utf-8")
    lowered = sql.lower()
    for column in (
        "reconciled_booking_id",
        "reconciliation_status",
        "reconciled_by",
        "reconciled_at",
    ):
        assert f"add column if not exists {column}" in lowered
    assert "existing_booking_linked" in lowered
    assert "create unique index if not exists uq_recruitment_audit_reconciled_source" in lowered
    assert "drop table" not in lowered
    assert "drop column" not in lowered
    assert "delete from" not in lowered


def test_domain_uses_required_locks_and_never_writes_auto_booking_audit():
    source = (REPO / "services" / "interview_reconciliation.py").read_text(
        encoding="utf-8"
    )
    assert "candidate_booking_lock(preliminary_candidate_id)" in source
    assert "FOR UPDATE OF m" in source
    assert "candidates_store WHERE id=%s FOR UPDATE" in source
    assert "mail_ai_analyses a WHERE mailbox_message_id=%s FOR SHARE" in source
    assert "interview_auto_booking_audit" not in source
