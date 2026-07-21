from datetime import datetime, timezone

import pytest

from core.ai_gateway import AIGatewayError
from services.recruitment_mail_agent import (
    _prompt_json, _manual_review_from_strong_context, clean_email, relevance_score, content_hash, validate_result, parse_model_json,
    routing_decision, _failure_review_result,
)

def valid_result():
    return {'schema_version':'selection_offer_event_v1','is_recruitment_related':True,'is_selection_or_offer_related':True,'should_create_review_record':True,'status':'SELECTED','confidence':.95,'ignore_reason':None,'candidate':{'name':None,'email':None},'company':{'name':None,'domain':None},'job':{'title':None,'employment_type':None,'location':None},'recruiter':{'name':None,'email':None},'interview':{k:None for k in ['date','time','timezone','mode','round','location','meeting_link']},'offer':{'offer_detected':False,'offer_letter_detected':False,'appointment_letter_detected':False,'offer_date':None,'offered_ctc':None,'currency':None,'joining_date':None,'offer_expiry_date':None},'attachments':[],'evidence':[{'source':'EMAIL_BODY','meaning':'SELECTED','text':'you have been selected'}],'risk_flags':[],'requires_manual_review':False,'summary':'Selected.','recommended_action':'Review.'}

def test_clean_email_removes_html_and_quoted_history():
    value=clean_email('<p>Your interview has been scheduled.</p>\nOn yesterday Recruiter wrote:\nold text')
    assert value=='Your interview has been scheduled.'

def test_mail_filter_tracks_interview_update_but_ignores_job_alert():
    invite=relevance_score('Interview scheduled','Your technical round is confirmed.',['invite.pdf'])
    alert=relevance_score('LinkedIn job alert','New jobs selected for you',[])
    assert invite >= .9
    assert alert == 0


def test_mail_filter_routes_assertive_calendar_invite_wording():
    invite=relevance_score(
        'Virtual Interview - Senior Full Stack Engineer (Front-End Focused)',
        'Please join the Virtual Interview at 12.30 pm on 21st July, 2026. Microsoft Teams meeting.',
    )
    assert invite >= .6


def test_ai_outage_keeps_strong_interview_invite_visible_for_review():
    subject='Virtual Interview - Senior Full Stack Engineer (Front-End Focused)'
    body='Please join the Virtual Interview at 12.30 pm on 21st July, 2026. Microsoft Teams meeting.'
    route=routing_decision(subject,body,sender_email='recruiter@example.com')
    result=_manual_review_from_strong_context(
        {'subject':subject,'body':body,'sent_at':datetime(2026,7,20,tzinfo=timezone.utc)},
        route['context'],
        AIGatewayError('timeout',code='OLLAMA_REQUEST_TIMEOUT'),
    )
    assert result['primary_status'] == 'INTERVIEW_CONFIRMED'
    assert result['business_domain'] == 'INTERVIEW_TRACKING'
    assert result['interview']['date'] == '2026-07-21'
    assert result['interview']['time'] == '12:30 PM'
    assert result['requires_manual_review'] is True

def test_mail_filter_uses_qualified_thread_context():
    interview=relevance_score('Re: update','Please see below.',[],[{'subject':'Technical round interview confirmation'}])
    selected=relevance_score('Re: update','Please see below.',[],[{'subject':'Selection update','body':'You have been selected for the role.'}])
    assert interview >= .9
    assert selected >= .9

def test_hash_is_deterministic():
    assert content_hash('same')==content_hash('same')
    assert content_hash('same')!=content_hash('different')

def test_confidence_rule_persists_low_and_medium_confidence_for_manual_review():
    message={'subject':'Selection update','body':'You have been selected for the role.'}
    low=valid_result();low['confidence']=.65
    validate_result(low,message)
    assert low['status'] == 'MANUAL_REVIEW_REQUIRED'
    assert low['classification'] == 'needs_review'
    medium=valid_result();medium['confidence']=.85
    validate_result(medium,message)
    assert medium['status'] == 'MANUAL_REVIEW_REQUIRED'
    assert medium['requires_manual_review'] is True

def test_invalid_status_is_rejected():
    row=valid_result();row['status']='MADE_UP'
    try:validate_result(row)
    except ValueError:return
    raise AssertionError('invalid status accepted')

def test_safe_json_repair_once():
    assert parse_model_json('```json\n{"status":"ok",}\n```') == {'status':'ok'}


def test_prompt_json_serializes_provider_datetime():
    payload = {"sent_at": datetime(2026, 7, 18, 10, 0, tzinfo=timezone.utc)}
    assert '"sent_at": "2026-07-18T10:00:00+00:00"' in _prompt_json(payload)

def test_non_iso_offer_dates_are_rejected():
    row=valid_result();row['offer']['joining_date']='12/07/2026'
    with pytest.raises(ValueError,match='invalid ISO date'):
        validate_result(row,{'subject':'Selection update','body':'You have been selected for the role.'})

def test_central_recruitment_model_routes_use_required_defaults(monkeypatch):
    from core.ai_model_routing import configured_model_routes
    for name in ('OLLAMA_PRIMARY_MODEL','OLLAMA_MAIL_MODEL','AI_RECRUITMENT_MODEL','AI_RECRUITMENT_VALIDATOR_MODEL','AI_RECRUITMENT_FALLBACK_MODEL','OLLAMA_VISION_MODEL'):
        monkeypatch.delenv(name,raising=False)
    assert configured_model_routes() == {
        'recruitment_email_primary':'qwen2.5:7b',
        'recruitment_email_validator':'qwen2.5:7b',
        'recruitment_document_vision':'qwen2.5vl:7b',
    }


def interview_result(status='INTERVIEW_CONFIRMED', classification='interview_confirmed'):
    row=valid_result();row.update(status=status,classification=classification,candidate_status='Interview Confirmed',confidence=96)
    row['interview'].update(date='2026-07-20',time='03:00 PM',timezone='Asia/Kolkata',mode='Online',round='L1',meeting_link='https://meet.test/room')
    row['evidence']=[{'source':'EMAIL_BODY','meaning':status,'text':'interview is scheduled for July 20, 2026 at 03:00 PM IST'}]
    return row


def test_interview_confidence_0_to_100_is_normalized_and_validated():
    row=interview_result()
    message={'subject':'Technical interview','body':'Your interview is scheduled for July 20, 2026 at 03:00 PM IST.'}
    validate_result(row,message)
    assert row['confidence']==.96
    assert row['classification']=='interview_confirmed'


@pytest.mark.parametrize(("field","value","match"),[("date",None,"ISO date"),("time","15:00","12-hour time"),("timezone",None,"timezone")])
def test_confirmed_interview_requires_explicit_schedule(field,value,match):
    row=interview_result();row['interview'][field]=value
    message={'subject':'Technical interview','body':'Your interview is scheduled for July 20, 2026 at 03:00 PM IST.'}
    with pytest.raises(ValueError,match=match):validate_result(row,message)


def test_shortlist_without_schedule_remains_informational():
    row=valid_result();row.update(status='INTERVIEW_SHORTLISTED',classification='interview_shortlisted',candidate_status='Interview Shortlisted')
    row['evidence']=[{'source':'EMAIL_BODY','meaning':'INTERVIEW_SHORTLISTED','text':'shortlisted for the next interview'}]
    validate_result(row,{'subject':'Update','body':'You have been shortlisted for the next interview. We will contact you later.'})
    assert row['classification']=='interview_shortlisted'


# Regression coverage for the "Ollama should not be required to reject
# obvious noise" fix. NAUKRI_WALKIN_* reproduces the exact production email
# (subject/body/sender) that was wrongly routed to the AI model and then,
# once Ollama was unreachable, wrongly forced into Needs Review.
NAUKRI_WALKIN_SUBJECT = "Reminder: Don’t Forget to attend these Walk-in's today"
NAUKRI_WALKIN_BODY = (
    "Reminder! Don’t forget to attend the walk-in job(s) you have applied to. "
    "Your walk-in reminder Urgent Opening DevOps Engineer Tcs 18 Jul walkin Interview "
    "Concepts Unlimited Date & time 2026-7-18, 9.00 AM - 11.30 AM Location Will share "
    "Be prepared to answer as well as ask questions to the recruiters. Team Naukri"
)


def test_deterministic_job_ad_is_not_routed_to_ai():
    """TEST 1: obvious deterministic noise must never reach the AI model."""
    route = routing_decision(NAUKRI_WALKIN_SUBJECT, NAUKRI_WALKIN_BODY, "", "reminder@naukri.com")
    assert route["send_to_ai"] is False


# Regression coverage for a follow-up finding: once the Needs Review filter
# worked, it surfaced real production noise the original fix missed — a bank
# transaction alert and two Naukri marketing emails, all pulled into AI by
# the ambiguous-recruitment fallback matching an isolated word ("offer" in a
# fraud-warning footer, "recruiter" in bulk marketing copy) anywhere in the
# email body.
def test_bank_transaction_alert_is_not_routed_to_ai():
    subject = "INR 13.00 was debited from your A/c no. XX2066."
    body = (
        "Dear Customer, here's the summary of your transaction: Amount Debited: "
        "INR 13.00 Account Number: XX2066 Transaction Info: UPI/P2M/127568896017. "
        "Regards, Axis Bank Ltd. RBI never deals with individuals for Savings "
        "Account, Current Account, Credit Card, Debit Card, etc. Don't be victim "
        "to such offers coming to you on phone or email in the name of RBI."
    )
    route = routing_decision(subject, body, "", "alerts@axis.bank.in")
    assert route["send_to_ai"] is False


def test_job_portal_recruiter_marketing_is_not_routed_to_ai():
    subject = "You have a new job in your inbox!"
    body = (
        "You have a job directly sent by recruiter! Apply to the jobs directly "
        "sent by recruiters. Also keep your profile updated to continue to get "
        "noticed by recruiters. Component Design Engineer Pimpri-Chinchwad."
    )
    route = routing_decision(subject, body, "", "donotreply_mailer@naukri.com")
    assert route["send_to_ai"] is False


def test_job_portal_safety_tips_are_not_routed_to_ai():
    subject = "How to make your job search safer"
    body = (
        "Keep yourself safe while searching for a job! Job scams are an "
        "unfortunate reality of the recruitment market. Beware of these common "
        "signs of fraud jobs. A job offer is a scam if you are asked to pay money."
    )
    route = routing_decision(subject, body, "", "info@naukri.com")
    assert route["send_to_ai"] is False


def test_ambiguous_cue_requires_a_whole_word_not_a_substring():
    """A plain `cue in text` check let "offer" match inside "offering" in an
    unrelated investment newsletter, forcing it through the AI pipeline."""
    subject = "New A- rated bond offering is now available"
    body = (
        "View the bond details and other important information. Update your "
        "email preferences here to choose the category of emails you wish to "
        "receive."
    )
    route = routing_decision(subject, body, "", "invest@stablebonds.in")
    assert route["send_to_ai"] is False


def test_genuine_offer_email_still_qualifies_for_ai():
    """The tightened word-boundary cue match must not lose real signal."""
    route = routing_decision(
        "Your Offer",
        "We are pleased to offer you the position of Software Engineer.",
        "", "hr@realcompany.invalid",
    )
    assert route["send_to_ai"] is True


def test_candidate_specific_walkin_confirmation_is_routed_to_ai():
    """TEST 2: a candidate-specific confirmed walk-in must still reach AI/validation."""
    route = routing_decision(
        "Walk-in interview confirmation",
        "Hi Gopichand, your interview with ABC Technologies is confirmed today at 2 PM IST.",
        "ABC Technologies HR", "hr@abctechnologies.invalid",
    )
    assert route["send_to_ai"] is True


def test_ollama_down_and_obvious_ad_is_audit_only_not_retry_pending():
    """TEST 3: Ollama unavailable + obvious deterministic ad -> Audit Only, never Needs Review."""
    message = {
        "subject": NAUKRI_WALKIN_SUBJECT, "body": NAUKRI_WALKIN_BODY,
        "sender_email": "reminder@naukri.com", "sender_name": "",
        "recipient_email": "candidate@test.invalid", "sent_at": "2026-07-18T13:38:53Z",
    }
    exc = AIGatewayError("Ollama connection failed", code="OLLAMA_CONNECTION_FAILED")
    result = _failure_review_result(message, exc)
    assert result["is_selection_or_offer_related"] is False
    assert result["should_create_review_record"] is False
    assert result["primary_status"] == "IGNORED_NOT_OFFER_RELATED"
    assert result["classification"] == "not_relevant"
    assert result["ai_status"] == "NOT_REQUIRED"
    assert result["validation_status"] == "NOT_REQUIRED"
    assert result["lifecycle_event"] == "NONE"
    assert result["interview_event"] == "NONE"
    assert result["requires_manual_review"] is False


def test_ollama_down_and_ambiguous_recruitment_email_is_retry_pending():
    """TEST 4: Ollama unavailable + genuinely ambiguous content -> AI_RETRY_PENDING, no lifecycle/interview event."""
    message = {
        "subject": "Update on your application",
        "body": "We wanted to update you on the status of your recent application with our team.",
        "sender_email": "talent@employer.invalid", "sender_name": "Talent Team",
        "recipient_email": "candidate@test.invalid", "sent_at": "2026-07-18T13:38:53Z",
    }
    exc = AIGatewayError("Ollama connection failed", code="OLLAMA_CONNECTION_FAILED")
    result = _failure_review_result(message, exc)
    assert result["primary_status"] == "MANUAL_REVIEW_REQUIRED"
    assert result["ai_status"] == "RETRY_PENDING"
    assert result["validation_status"] == "RETRY_PENDING"
    assert result["lifecycle_event"] == "NONE"


@pytest.mark.parametrize("subject", [
    "You’re now open to work - we can help you get noticed",
    "Aparna Kartik and others share their thoughts on LinkedIn",
    "Job application successful.",
    "You applied for 5 jobs on 17 Jul",
    "Reddy Charan, add Subarta Chandra as a contact",
])
def test_known_profile_network_and_application_noise_skips_ai(subject):
    route = routing_decision(
        subject, "This notification does not confirm selection, offer, or joining.",
        sender_email="messages-noreply@linkedin.com",
    )
    assert route["send_to_ai"] is False
