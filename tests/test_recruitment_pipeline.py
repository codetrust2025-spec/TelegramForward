from pathlib import Path

from services import recruitment_mail_agent as agent


def structured(status="INTERVIEW_SCHEDULED", confidence=.95):
    return {
        "schema_version": "recruitment_event_v1",
        "is_recruitment_related": True,
        "primary_status": status,
        "confidence": confidence,
        "candidate": {"name": None, "email": None},
        "company": {"name": "Test Company", "domain": "test.invalid"},
        "job": {"title": "Test Role", "employment_type": None, "location": None},
        "recruiter": {"name": None, "email": None},
        "interview": {key: None for key in ["date", "time", "timezone", "mode", "round", "location", "meeting_link"]},
        "offer": {"offer_detected": False, "offer_letter_detected": False, "offer_date": None, "offered_ctc": None, "currency": None, "joining_date": None, "offer_expiry_date": None},
        "attachments": [], "evidence": [], "risk_flags": [],
        "requires_manual_review": False, "summary": "Detected.", "recommended_action": "Review.",
    }


def message(subject="Interview scheduled", body="Your technical interview is scheduled."):
    return {"provider_message_id": "message-1", "provider_thread_id": "thread-1", "sender_email": "jobs" + "@" + "test.invalid", "recipient_email": "candidate" + "@" + "test.invalid", "subject": subject, "sent_at": "2026-07-13T10:00:00Z", "body": body}


def test_relevant_message_runs_pipeline_and_creates_event(monkeypatch):
    saved=[];created=[]
    monkeypatch.setattr(agent.store, "insert_message", lambda mailbox, decoded, score: ({"id": "stored-message"}, True))
    monkeypatch.setattr(agent.store, "is_duplicate_content", lambda *args: False)
    monkeypatch.setattr(agent.store, "save_attachment", lambda mid, attachment: saved.append((mid, attachment)))
    monkeypatch.setattr(agent.store, "create_event", lambda cid, mid, result, **meta: created.append((cid, mid, result, meta)) or {"id": "event-1", "primary_status": result["primary_status"]})
    monkeypatch.setattr(agent, "analyze", lambda decoded, attachments: (structured(), "configured-test-model", 12))
    monkeypatch.setattr("services.recruitment_notifications.notify_detection", lambda event: None)
    result=agent.process_message({"id": "mailbox-1", "candidate_id": "candidate-1"}, message(), [{"filename": "invite.txt", "data": None, "checksum": "checksum-1"}])
    assert result["primary_status"] == "INTERVIEW_SCHEDULED"
    assert saved and created
    assert created[0][3]["model"] == "configured-test-model"


def test_irrelevant_and_duplicate_messages_do_not_reach_ai(monkeypatch):
    analyzed=[];statuses=[]
    monkeypatch.setattr(agent.store, "insert_message", lambda mailbox, decoded, score: ({"id": "stored-message"}, True))
    monkeypatch.setattr(agent.store, "is_duplicate_content", lambda *args: False)
    monkeypatch.setattr(agent, "analyze", lambda *args: analyzed.append(True))
    assert agent.process_message({"id": "mailbox-1", "candidate_id": "candidate-1"}, message("Weekly newsletter", "General product news."), []) is None
    assert not analyzed
    monkeypatch.setattr(agent.store, "is_duplicate_content", lambda *args: True)
    monkeypatch.setattr(agent.store, "mark_message_status", lambda mid, status: statuses.append(status))
    assert agent.process_message({"id": "mailbox-1", "candidate_id": "candidate-1"}, message(), []) is None
    assert statuses == ["DUPLICATE_CONTENT"] and not analyzed


def test_migration_contains_all_required_tables_and_indexes():
    sql=(Path(__file__).parents[1] / "core" / "migrations" / "001_recruitment_mail_tracking.sql").read_text("utf-8").lower()
    tables={"candidate_mailboxes", "mailbox_messages", "mailbox_attachments", "mailbox_attachment_cache", "ai_recruitment_events", "candidate_status_history", "offer_verification_cases", "mailbox_sync_jobs", "recruitment_audit_log", "recruitment_review_flags"}
    for table in tables:
        assert f"create table if not exists {table}" in sql
    assert "unique(mailbox_id,provider_message_id)" in sql
    assert sql.count("create index if not exists") >= 6
