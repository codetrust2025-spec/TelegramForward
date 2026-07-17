from core import recruitment_mail_store as store
from pathlib import Path


def test_every_requested_classification_is_stable():
    assert store.CANONICAL_CLASSIFICATIONS == {
        'job_selection_confirmed','offer_received','offer_accepted','offer_declined',
        'offer_revoked','joining_confirmed','joining_date_updated','onboarding_started',
        'background_verification','document_verification','compensation_confirmation',
        'interview_update','interview_shortlisted','interview_confirmed','interview_rescheduled',
        'interview_cancelled','candidate_rejected','needs_review','not_relevant',
    }


def test_legacy_statuses_map_without_breaking_existing_records():
    assert store.canonical_classification(status='OFFER_LETTER_RECEIVED') == 'offer_received'
    assert store.canonical_classification(status='FINAL_SELECTION_CONFIRMED') == 'job_selection_confirmed'
    assert store.canonical_classification(status='INTERVIEW_UPDATE') == 'interview_update'
    assert store.canonical_classification(status='INTERVIEW_CONFIRMED') == 'interview_confirmed'


def test_priority_and_review_thresholds(monkeypatch):
    monkeypatch.setenv('OLLAMA_CONFIDENCE_THRESHOLD','0.75')
    assert store.notification_priority('offer_received',confidence=.94)=='high'
    assert store.notification_priority('document_verification',confidence=.90)=='medium'
    assert store.notification_priority('candidate_rejected',confidence=.90)=='informational'
    assert store.notification_priority('offer_received',confidence=.70)=='review_required'


def test_auto_booking_migration_is_additive_and_idempotent():
    sql=Path('core/migrations/008_recruitment_mail_auto_booking.sql').read_text(encoding='utf-8').lower()
    for table in ('gmail_pubsub_deliveries','interview_mail_analyses','interview_auto_booking_audit'):
        assert f'create table if not exists {table}' in sql
    assert 'unique(gmail_message_id, classification)' in sql
    assert 'drop table' not in sql and 'delete from' not in sql


def test_required_realtime_event_contract_is_emitted():
    source=Path('services/recruitment_mail_agent.py').read_text(encoding='utf-8')
    worker=Path('workers/recruitment_mail_worker.py').read_text(encoding='utf-8')
    booking=Path('services/interview_auto_booking.py').read_text(encoding='utf-8')
    for event in ('mail_received','mail_ai_analyzing','interview_detected','auto_booking_started','slot_auto_booked','slot_booking_blocked','interview_rescheduled','interview_cancelled','candidate_status_updated','notification_created','mail_processing_failed'):
        assert event in source or event in worker or event in booking
