from core.recruitment_mail_store import summarize_selection_tracking_events
from services.recruitment_mail_agent import _failure_review_result, prefilter_decision
from services.recruitment_semantics import (
    classify_context,
    redact_sensitive_text,
)
from workers import recruitment_mail_worker as worker_module


def test_recruiter_questionnaire_has_no_lifecycle_event():
    body = """Full Name:
Experience:
Current Company:
Expected CTC:
Offer in Hand:
Date of Joining:
Contact No:
"""
    result = classify_context("Candidate details required", body)
    assert result["email_intent"] == "RECRUITER_QUESTIONNAIRE"
    assert result["is_job_outcome"] is False
    assert result["lifecycle_event"] == "NONE"
    assert prefilter_decision("Candidate details required", body)["qualified"] is False


def test_payslip_joining_date_is_historical_metadata():
    text = "PAYSLIP FOR THE MONTH OF APRIL 2026 Employee ID MT-11822 Date Of Joining: 04-11-2023 Working Days: 30"
    result = classify_context("Payslip", "Attached", attachments=[{"filename": "April.pdf", "text": text}])
    assert result["document_type"] == "PAYSLIP"
    assert result["historical_employment_evidence"] is True
    assert result["lifecycle_event"] == "NONE"


def test_joining_confirmation_is_not_joined():
    result = classify_context("Joining", "Your joining date is confirmed as 25 July 2026.")
    assert result["email_intent"] == "JOINING_CONFIRMATION"
    assert result["lifecycle_event"] == "JOINING_CONFIRMED"


def test_actual_employment_start_is_joined():
    result = classify_context("Welcome", "We confirm that you officially joined ABC Technologies today.")
    assert result["email_intent"] == "ACTUAL_JOINING_CONFIRMATION"
    assert result["lifecycle_event"] == "JOINED"


def test_offer_statement_is_offer_received():
    result = classify_context("Your offer", "We are pleased to offer you the Software Engineer position.")
    assert result["email_intent"] == "OFFER_LETTER"
    assert result["lifecycle_event"] == "OFFER_LETTER_RECEIVED"


def test_offer_question_is_not_an_offer_event():
    result = classify_context("Candidate details", "Do you currently have an offer in hand?")
    assert result["lifecycle_event"] == "NONE"
    assert result["is_question"] is True


def test_joining_date_request_is_not_confirmation():
    result = classify_context("Joining", "Please share your date of joining.")
    assert result["lifecycle_event"] == "NONE"
    assert result["email_intent"] == "CANDIDATE_DETAILS_REQUEST"


def test_naukri_job_ad_keywords_do_not_create_outcome():
    result = classify_context(
        "Job | AWS Devops in Hyderabad",
        "Shortlisted candidates may receive an offer. Joining details will follow. Experience: 5 years. Location: Hyderabad. Skills: AWS. Job description attached.",
        sender_email="jobs@naukri.com",
    )
    assert result["email_intent"] == "JOB_ADVERTISEMENT"
    assert result["lifecycle_event"] == "NONE"


def _event(event_id, candidate_id, status, *, canonical=None, validation="AUTO_VALIDATED", review="AUTO_VALIDATED"):
    return {
        "id": event_id,
        "candidate_id": candidate_id,
        "canonical_candidate_id": canonical,
        "primary_status": status,
        "validation_status": validation,
        "review_status": review,
    }


def test_repeated_joining_emails_count_one_candidate():
    summary = summarize_selection_tracking_events([
        _event("e1", "c1", "JOINING_CONFIRMED"),
        _event("e2", "c1", "JOINING_CONFIRMED"),
        _event("e3", "c1", "JOINING_CONFIRMED"),
    ])
    assert summary["metrics"]["joining_confirmed"] == 1


def test_joining_confirmed_never_inflates_joined_metric():
    summary = summarize_selection_tracking_events([
        _event(f"e{i}", f"c{i}", "JOINING_CONFIRMED") for i in range(5)
    ])
    assert summary["metrics"]["joining_confirmed"] == 5
    assert summary["metrics"]["joined"] == 0


def test_duplicate_candidate_ids_count_as_one_canonical_person():
    summary = summarize_selection_tracking_events([
        _event("e1", "alias-a", "JOINING_CONFIRMED", canonical="person-1"),
        _event("e2", "alias-b", "JOINING_CONFIRMED", canonical="person-1"),
    ])
    assert summary["metrics"]["joining_confirmed"] == 1


def test_ollama_failure_creates_retry_pending_none_event():
    result = _failure_review_result(
        {"subject": "Joining", "body": "Your joining date is confirmed as 25 July 2026."},
        RuntimeError("offline"),
    )
    assert result["primary_status"] == "MANUAL_REVIEW_REQUIRED"
    assert result["lifecycle_event"] == "NONE"
    assert result["validation_status"] == "RETRY_PENDING"


def test_ollama_recovery_reprocesses_idempotently(monkeypatch):
    calls = []
    row = {
        "id": "stored-1", "mailbox_id": "mb1", "mailbox_candidate_id": "c1",
        "provider_message_id": "gmail-1", "subject": "Offer", "body_text": "Offer body",
        "attachments": [],
    }
    monkeypatch.setattr("core.ai_gateway.health", lambda **_kwargs: {"endpoint_reachable": True, "model_available": True})
    monkeypatch.setattr(worker_module.store, "retry_pending_messages", lambda **_kwargs: [row])
    monkeypatch.setattr(worker_module.store, "schedule_ai_retry", lambda message_id, **kwargs: calls.append((message_id, kwargs)))
    monkeypatch.setattr(worker_module, "process_message", lambda *args, **kwargs: {"id": "same-event", "validation_status": "AUTO_VALIDATED"})
    worker_module.RecruitmentMailWorker().process_ai_recovery()
    assert calls == [("stored-1", {"succeeded": True})]


def test_detection_evidence_masks_sensitive_identifiers():
    redacted = redact_sensitive_text("PAN: ABCDE1234F Bank Account Number: 123456789012 UAN: 123456789012")
    assert "ABCDE1234F" not in redacted
    assert "123456789012" not in redacted
