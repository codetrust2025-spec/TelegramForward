"""A refusal by our own schema check must not be retried as an outage.

`analyze()` raises AIGatewayError for both "the service is unreachable" and
"the model answered and the answer failed validation". `process_message`
treated them identically and put the mail on the infrastructure retry path.

The second kind mostly reproduces itself: identical input, identical refusal.
Two Production mails reached ten attempts on OLLAMA_SCHEMA_VALIDATION_FAILED —
a TCS reminder stating a date but no time at all, and an NLB questionnaire that
is not an interview. Both refusals were correct. Left alone they would have
been parked as MAX_ATTEMPTS_EXHAUSTED, which names the wrong cause and buries a
decision an operator can act on.

`VALIDATION_FAILED` is the status the outcome audit already reports as a
SCHEMA_VALIDATION_FAILED gap; until this fix nothing ever produced it.
"""

import pytest

from core.ai_gateway import AIGatewayError
from services import recruitment_mail_agent as agent


class FakeStore:
    def __init__(self, retry_count):
        self.row = {"id": "m1", "ai_retry_count": retry_count, "processing_status": "AI_QUEUED"}
        self.status_calls = []
        self.analysis_calls = []

    # ── the calls process_message makes on the failure path ──
    def insert_message(self, mailbox, decoded, score):
        return self.row, True

    def mark_message_status(self, message_id, status, *, reason=None, cleanup_version=None, error_code=None):
        self.status_calls.append({"status": status, "reason": reason, "error_code": error_code})

    def record_analysis(self, message_id, candidate_id, result, *, model, processing_status,
                        error_code=None, error_message=None):
        self.analysis_calls.append({"processing_status": processing_status, "error_code": error_code})

    # ── everything else process_message touches, made inert ──
    def is_duplicate_content(self, *a, **k): return False
    def is_duplicate_offer_attachment(self, *a, **k): return False
    def mark_reprocessed(self, *a, **k): pass
    def archive_event_for_message(self, *a, **k): pass
    def resume_interrupted_ai(self, *a, **k): pass


def _run(monkeypatch, *, retry_count, code):
    """Drive process_message to the analyze() failure branch."""
    store = FakeStore(retry_count)
    monkeypatch.setattr(agent, "store", store)
    monkeypatch.setattr(agent, "_publish", lambda *a, **k: None)
    monkeypatch.setattr(agent, "_publish_ignored_interview", lambda *a, **k: None)
    monkeypatch.setattr(agent, "routing_decision",
                        lambda *a, **k: {"send_to_ai": True, "score": 0.9, "reason": "OK", "context": {}})
    monkeypatch.setattr("services.calendar_invite_parser.trusted_interview_result", lambda *a, **k: None)

    def boom(*a, **k):
        raise AIGatewayError("failed", code=code)

    monkeypatch.setattr(agent, "analyze", boom)

    mailbox = {"id": "mb1", "candidate_id": "c1", "email_address": "candidate@test.invalid"}
    decoded = {"provider_message_id": "gm1", "provider_thread_id": "gt1",
               "subject": "Face-to-Face Interview with TCS on 18-Jul-2026",
               "body": "The interview is scheduled for Saturday, 18 July 2026.",
               "sender_email": "recruiter@test.invalid", "sent_at": "2026-07-16T09:00:00+00:00"}
    agent.process_message(mailbox, decoded, [])
    return store


def test_a_repeated_validation_failure_is_parked_not_retried(monkeypatch):
    store = _run(monkeypatch, retry_count=10, code="OLLAMA_SCHEMA_VALIDATION_FAILED")

    assert store.status_calls, "the message must be marked"
    marked = store.status_calls[-1]
    assert marked["status"] == "VALIDATION_FAILED"
    assert marked["error_code"] == "OLLAMA_SCHEMA_VALIDATION_FAILED"
    assert all(call["status"] != "AI_RETRY_PENDING" for call in store.status_calls)


def test_the_parked_message_records_why_for_the_audit(monkeypatch):
    store = _run(monkeypatch, retry_count=10, code="OLLAMA_SCHEMA_VALIDATION_FAILED")

    assert store.analysis_calls, "the refusal must leave an analysis behind"
    assert store.analysis_calls[-1]["processing_status"] == "VALIDATION_FAILED"
    assert store.analysis_calls[-1]["error_code"] == "OLLAMA_SCHEMA_VALIDATION_FAILED"


def test_the_first_validation_failures_still_get_a_genuine_retry(monkeypatch):
    """Sampling can turn a rejected answer into a valid one, so try a few times."""
    store = _run(monkeypatch, retry_count=0, code="OLLAMA_SCHEMA_VALIDATION_FAILED")

    assert store.status_calls[-1]["status"] == "AI_RETRY_PENDING"
    assert store.status_calls[-1]["error_code"] == "OLLAMA_SCHEMA_VALIDATION_FAILED"


@pytest.mark.parametrize("code", [
    "OLLAMA_REQUEST_TIMEOUT", "OLLAMA_UNAVAILABLE", "OLLAMA_INTERNAL_ERROR",
    "OLLAMA_INVALID_JSON",
])
def test_a_real_outage_still_retries_however_many_attempts_have_run(monkeypatch, code):
    """Only our own schema refusal is deterministic; an outage must keep retrying."""
    store = _run(monkeypatch, retry_count=11, code=code)

    assert store.status_calls[-1]["status"] == "AI_RETRY_PENDING"
    assert store.status_calls[-1]["error_code"] == code


def test_the_failure_code_reaches_the_field_the_queue_is_read_from(monkeypatch):
    """`ignore_reason` keeps stale text; `ai_last_error_code` is the live signal.

    All 24 stuck messages carried a null code, which is what made the cause hard
    to find at all.
    """
    store = _run(monkeypatch, retry_count=0, code="OLLAMA_REQUEST_TIMEOUT")
    assert store.status_calls[-1]["error_code"] == "OLLAMA_REQUEST_TIMEOUT"
    assert store.status_calls[-1]["reason"] == "OLLAMA_REQUEST_TIMEOUT"


def test_the_audit_reports_this_status_as_a_schema_validation_gap():
    """The consumer already existed; this pins the producer to its contract."""
    import inspect
    from core import recruitment_mail_audit_store as audit

    src = inspect.getsource(audit)
    assert '"VALIDATION_FAILED"' in src
    assert "GAP_SCHEMA_VALIDATION_FAILED" in src
    assert "VALIDATION_FAILED" in inspect.getsource(agent.process_message)
