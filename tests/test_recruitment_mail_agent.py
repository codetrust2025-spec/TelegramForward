from datetime import datetime, timezone

import pytest

from services.recruitment_mail_agent import _prompt_json, clean_email, relevance_score, content_hash, validate_result, parse_model_json

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
        'recruitment_email_primary':'gemma4:12b',
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
