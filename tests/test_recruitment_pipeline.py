from pathlib import Path

import pytest

from services import recruitment_mail_agent as agent


def structured(status="OFFER_LETTER_RECEIVED", confidence=.95, evidence_text="offer letter"):
    return {
        "schema_version": "selection_offer_event_v1",
        "is_recruitment_related": True,
        "is_selection_or_offer_related": status not in agent.INTERNAL_STATUSES,
        "should_create_review_record": status not in agent.INTERNAL_STATUSES,
        "status": status,
        "confidence": confidence,
        "ignore_reason": None,
        "candidate": {"name": None, "email": None},
        "company": {"name": "Test Company", "domain": "test.invalid"},
        "job": {"title": "Test Role", "employment_type": None, "location": None},
        "recruiter": {"name": None, "email": None},
        "interview": {key: None for key in ["date", "time", "timezone", "mode", "round", "location", "meeting_link"]},
        "offer": {"offer_detected": True, "offer_letter_detected": status == "OFFER_LETTER_RECEIVED", "appointment_letter_detected": status == "APPOINTMENT_LETTER_RECEIVED", "offer_date": None, "offered_ctc": None, "currency": None, "joining_date": None, "offer_expiry_date": None},
        "attachments": [], "evidence": [{"source":"EMAIL_SUBJECT","meaning":status,"text":evidence_text}], "risk_flags": [],
        "requires_manual_review": False, "summary": "Detected.", "recommended_action": "Review.",
    }


def message(subject="Offer letter", body="We are pleased to offer you the Test Role."):
    return {"provider_message_id": "message-1", "provider_thread_id": "thread-1", "sender_email": "jobs" + "@" + "test.invalid", "recipient_email": "candidate" + "@" + "test.invalid", "subject": subject, "sent_at": "2026-07-13T10:00:00Z", "body": body}


def test_relevant_message_runs_pipeline_and_creates_event(monkeypatch):
    saved=[];created=[]
    monkeypatch.setattr(agent.store, "insert_message", lambda mailbox, decoded, score: ({"id": "stored-message"}, True))
    monkeypatch.setattr(agent.store, "is_duplicate_content", lambda *args: False)
    monkeypatch.setattr(agent.store, "is_duplicate_offer_attachment", lambda *args: False)
    monkeypatch.setattr(agent.store, "is_duplicate_thread_status", lambda *args: False)
    monkeypatch.setattr(agent.store, "save_attachment", lambda mid, attachment: saved.append((mid, attachment)))
    monkeypatch.setattr(agent.store, "create_event", lambda cid, mid, result, **meta: created.append((cid, mid, result, meta)) or {"id": "event-1", "primary_status": result["primary_status"]})
    monkeypatch.setattr(agent, "analyze", lambda decoded, attachments: ({**structured(),"primary_status":"OFFER_LETTER_RECEIVED"}, "configured-test-model", 12))
    monkeypatch.setattr("services.recruitment_notifications.notify_detection", lambda event: None)
    result=agent.process_message({"id": "mailbox-1", "candidate_id": "candidate-1"}, message(), [{"filename": "invite.txt", "data": None, "checksum": "checksum-1"}])
    assert result["primary_status"] == "OFFER_LETTER_RECEIVED"
    assert saved and created
    assert created[0][3]["model"] == "configured-test-model"


def test_irrelevant_and_duplicate_messages_do_not_reach_ai(monkeypatch):
    analyzed=[];statuses=[]
    monkeypatch.setattr(agent.store, "insert_message", lambda mailbox, decoded, score: ({"id": "stored-message"}, True))
    monkeypatch.setattr(agent.store, "is_duplicate_content", lambda *args: False)
    monkeypatch.setattr(agent.store, "mark_message_status", lambda mid, status, **kwargs: statuses.append(status))
    monkeypatch.setattr(agent, "analyze", lambda *args: analyzed.append(True))
    assert agent.process_message({"id": "mailbox-1", "candidate_id": "candidate-1"}, message("Weekly newsletter", "General product news."), []) is None
    assert not analyzed
    assert statuses == ["IGNORED_NOT_OFFER_RELATED"]
    statuses.clear()
    monkeypatch.setattr(agent.store, "is_duplicate_content", lambda *args: True)
    assert agent.process_message({"id": "mailbox-1", "candidate_id": "candidate-1"}, message(), []) is None
    assert statuses == ["DUPLICATE_CONTENT"] and not analyzed


def test_job_recommendations_and_interviews_are_not_tracked(monkeypatch):
    analyzed=[]; created=[]; notified=[]
    monkeypatch.setattr(agent.store, "insert_message", lambda mailbox, decoded, score: ({"id": "stored-message"}, True))
    monkeypatch.setattr(agent.store, "is_duplicate_content", lambda *args: False)
    monkeypatch.setattr(agent.store, "mark_message_status", lambda *args, **kwargs: None)
    monkeypatch.setattr(agent.store, "create_event", lambda *args, **kwargs: created.append(True))
    monkeypatch.setattr(agent, "analyze", lambda *args: analyzed.append(True))
    monkeypatch.setattr("services.recruitment_notifications.notify_detection", lambda event: notified.append(event))
    mailbox={"id":"mailbox-1","candidate_id":"candidate-1"}
    assert agent.process_message(mailbox,message("Job recommendations for you | foundit","Apply now to matching jobs."),[]) is None
    assert agent.process_message(mailbox,message("Technical interview confirmed","Your interview is scheduled tomorrow."),[]) is None
    assert not analyzed and not created and not notified


@pytest.mark.parametrize(("subject", "body", "reason"), [
    ("Recommended jobs based on your profile", "New roles are waiting for you.", "JOB_RECOMMENDATION"),
    ("Your interview has been scheduled", "Join the interview tomorrow.", "INTERVIEW"),
    ("Coding test invitation", "Complete the assessment.", "ASSESSMENT"),
    ("Thank you for applying", "Your application is under review.", "APPLICATION_UPDATE"),
    ("Weekly career newsletter", "Upgrade account and apply now.", "JOB_PORTAL_MARKETING"),
    ("Regret to inform", "You were not selected.", "REJECTION"),
])
def test_ordinary_recruitment_mail_is_deterministically_ignored(subject, body, reason):
    decision = agent.prefilter_decision(subject, body, sender_email="alerts@foundit.in")
    assert decision == {
        "qualified": False,
        "score": 0.0,
        "status": "IGNORED_NOT_OFFER_RELATED",
        "evidence": [],
        "ignore_reason": reason,
    }


def test_selected_and_joining_confirmations_pass_the_strict_filter():
    assert agent.relevance_score("Congratulations on your selection","You have been selected for the role.") >= .55
    assert agent.relevance_score("Joining confirmation","Your date of joining is 20 July 2026.") >= .55
    assert agent.relevance_score("Job recommendations for you","This employer may offer a good opportunity.") == 0


def test_shortlisted_with_explicit_joining_date_uses_strongest_full_message_evidence():
    decision=agent.prefilter_decision(
        "Congratulations and Next Steps – Data Engineer Role",
        "Congratulations on being shortlisted for the role of Data Engineer. Your date of joining will be 15th July 2026. ONNI GLOBAL SERVICES INDIA PVT. LTD.",
        sender_email="hr@onniglobal.in",
    )
    assert decision["qualified"] is True
    assert decision["status"] == "JOINING_CONFIRMED"
    assert decision["joining_date"] == "2026-07-15"
    assert decision["job_title"] == "Data Engineer"
    assert "ONNI GLOBAL SERVICES" in decision["company_name"]
    assert decision["score"] >= .90
    assert decision["requires_manual_review"] is True
    assert "WORDING_STATUS_CONFLICT" in decision["risk_flags"]
    assert {item["source"] for item in decision["evidence"]} >= {"EMAIL_BODY","EMAIL_SUBJECT"}


def test_shortlist_only_stays_out_but_stronger_offer_evidence_wins():
    generic=agent.prefilter_decision("Application update","You have been shortlisted for the technical interview.")
    assert generic["qualified"] is False
    assert generic["ignore_reason"] == "SHORTLIST_ONLY"
    assert agent.prefilter_decision("Next steps","You have been shortlisted. We are planning to release your offer.")["status"] == "OFFER_INDICATION"
    assert agent.prefilter_decision("Documents","You have been shortlisted. Please find your offer letter attached.")["status"] == "OFFER_LETTER_RECEIVED"
    onboarding=agent.prefilter_decision("Next steps","You have been shortlisted. Please complete onboarding before joining on July 15.")
    assert onboarding["status"] in {"POST_SELECTION_ONBOARDING","JOINING_CONFIRMED"}


@pytest.mark.parametrize(("subject", "body", "expected"), [
    ("Congratulations! You have been selected", "You have been selected for the role.", "SELECTED"),
    ("Offer update", "Your offer is currently being processed.", "OFFER_IN_PROGRESS"),
    ("Offer Letter - Data Engineer", "Please find your offer letter attached.", "OFFER_LETTER_RECEIVED"),
    ("Offer acceptance confirmed", "We have accepted your offer acceptance.", "OFFER_ACCEPTED"),
    ("Joining confirmation", "Your joining date is 20 July 2026.", "JOINING_CONFIRMED"),
])
def test_strong_success_signals_are_qualified(subject, body, expected):
    decision=agent.prefilter_decision(subject,body)
    assert decision["qualified"] is True
    assert decision["status"] == expected
    assert decision["evidence"]


def test_appointment_attachment_requires_document_content():
    filename_only=agent.prefilter_decision("Document attached","",attachments=[{"filename":"Appointment_Letter.pdf","text":""}])
    confirmed=agent.prefilter_decision("Document attached","",attachments=[{"filename":"Appointment_Letter.pdf","text":"This document confirms employment with ABC."}])
    assert filename_only["qualified"] is False
    assert confirmed["status"] == "APPOINTMENT_LETTER_RECEIVED"


def test_context_dependent_joining_background_and_salary_rules():
    assert agent.prefilter_decision("Joining","Please confirm your date of joining.")["qualified"] is False
    thread=[{"subject":"Offer letter","body":"You have been selected for the role."}]
    assert agent.prefilter_decision("Joining","Please confirm your date of joining.",thread_context=thread)["status"] == "JOINING_CONFIRMED"
    assert agent.prefilter_decision("Background verification initiated","Please provide documents.")["qualified"] is False
    assert agent.prefilter_decision("Salary discussion","Let us discuss compensation.")["qualified"] is False
    background=agent.prefilter_decision("Background verification initiated","Your offer is approved. Complete background verification.")
    salary=agent.prefilter_decision("Salary discussion","You have been selected. Let us continue the salary discussion.")
    assert background["status"] in {"OFFER_APPROVED", "POST_SELECTION_ONBOARDING"}
    assert salary["status"] in {"SELECTED", "OFFER_INDICATION"}


def test_portal_mail_with_explicit_selection_is_not_blocked_by_sender():
    decision=agent.prefilter_decision(
        "Congratulations, you have been selected by ABC Company",
        "You have been selected for the position.",
        sender_name="foundit", sender_email="alerts@foundit.in",
    )
    assert decision["qualified"] is True
    assert decision["status"] == "SELECTED"


def test_validation_enforces_evidence_and_manual_review_confidence():
    medium=structured("OFFER_INDICATION",.85,"we are pleased to offer you")
    source=message("We are pleased to offer you","Details follow.")
    agent.validate_result(medium,source,[])
    assert medium["status"] == "MANUAL_REVIEW_REQUIRED"
    assert medium["confidence"] == .85
    unsupported=structured("SELECTED",.95,"invented evidence")
    with pytest.raises(ValueError,match="unsupported"):
        agent.validate_result(unsupported,message("Congratulations","You have been selected."),[])


def test_low_confidence_result_is_not_visible():
    low=structured("SELECTED",.79,"you have been selected")
    agent.validate_result(low,message("You have been selected","Details."),[])
    assert low["status"] == "IGNORED_LOW_CONFIDENCE"
    assert low["should_create_review_record"] is False


def test_non_outcome_ai_status_is_discarded(monkeypatch):
    statuses=[];created=[]
    monkeypatch.setattr(agent.store,"insert_message",lambda *args:({"id":"stored-message"},True))
    monkeypatch.setattr(agent.store,"is_duplicate_content",lambda *args:False)
    monkeypatch.setattr(agent.store,"is_duplicate_offer_attachment",lambda *args:False)
    monkeypatch.setattr(agent.store,"mark_message_status",lambda mid,status,**kwargs:statuses.append(status))
    monkeypatch.setattr(agent.store,"create_event",lambda *args,**kwargs:created.append(True))
    ignored={**structured("IGNORED_NOT_OFFER_RELATED"),"primary_status":"IGNORED_NOT_OFFER_RELATED","is_selection_or_offer_related":False,"should_create_review_record":False,"ignore_reason":"INTERVIEW"}
    monkeypatch.setattr(agent,"analyze",lambda *args:(ignored,"test",1))
    result=agent.process_message({"id":"mailbox-1","candidate_id":"candidate-1"},message(),[])
    assert result is None
    assert statuses == ["IGNORED_NOT_OFFER_RELATED"]
    assert not created


def test_migration_contains_all_required_tables_and_indexes():
    sql=(Path(__file__).parents[1] / "core" / "migrations" / "001_recruitment_mail_tracking.sql").read_text("utf-8").lower()
    tables={"candidate_mailboxes", "mailbox_messages", "mailbox_attachments", "mailbox_attachment_cache", "ai_recruitment_events", "candidate_status_history", "offer_verification_cases", "mailbox_sync_jobs", "recruitment_audit_log", "recruitment_review_flags"}
    for table in tables:
        assert f"create table if not exists {table}" in sql
    assert "unique(mailbox_id,provider_message_id)" in sql
    assert sql.count("create index if not exists") >= 6


def test_job_outcome_migration_archives_old_broad_matches():
    sql=(Path(__file__).parents[1] / "core" / "migrations" / "002_recruitment_mail_job_outcomes.sql").read_text("utf-8").lower()
    assert "false_positive" in sql
    assert "ignored_not_job_outcome" in sql
    assert "manual_review_required" in sql
    assert "job-outcome filter v2" in sql
    precision=(Path(__file__).parents[1] / "core" / "migrations" / "003_recruitment_mail_selection_offer_precision.sql").read_text("utf-8").lower()
    assert "ignored_not_offer_related" in precision
    assert "ignore_reason" in precision
    assert "ignored_at" in precision
    assert "cleanup_version" in precision
    assert "offer_case_key" in precision
