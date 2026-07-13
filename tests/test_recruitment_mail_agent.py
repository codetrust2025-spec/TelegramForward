import pytest

from services.recruitment_mail_agent import clean_email, relevance_score, content_hash, validate_result, parse_model_json

def valid_result():
    return {'schema_version':'selection_offer_event_v1','is_recruitment_related':True,'is_selection_or_offer_related':True,'should_create_review_record':True,'status':'SELECTED','confidence':.95,'ignore_reason':None,'candidate':{'name':None,'email':None},'company':{'name':None,'domain':None},'job':{'title':None,'employment_type':None,'location':None},'recruiter':{'name':None,'email':None},'interview':{k:None for k in ['date','time','timezone','mode','round','location','meeting_link']},'offer':{'offer_detected':False,'offer_letter_detected':False,'appointment_letter_detected':False,'offer_date':None,'offered_ctc':None,'currency':None,'joining_date':None,'offer_expiry_date':None},'attachments':[],'evidence':[{'source':'EMAIL_BODY','meaning':'SELECTED','text':'you have been selected'}],'risk_flags':[],'requires_manual_review':False,'summary':'Selected.','recommended_action':'Review.'}

def test_clean_email_removes_html_and_quoted_history():
    value=clean_email('<p>Your interview has been scheduled.</p>\nOn yesterday Recruiter wrote:\nold text')
    assert value=='Your interview has been scheduled.'

def test_selection_offer_filter_ignores_invite_and_job_alert():
    invite=relevance_score('Interview scheduled','Your technical round is confirmed.',['invite.pdf'])
    alert=relevance_score('LinkedIn job alert','New jobs selected for you',[])
    assert invite == 0
    assert alert == 0

def test_selection_offer_filter_uses_qualified_thread_context():
    ignored=relevance_score('Re: update','Please see below.',[],[{'subject':'Technical round interview confirmation'}])
    selected=relevance_score('Re: update','Please see below.',[],[{'subject':'Selection update','body':'You have been selected for the role.'}])
    assert ignored == 0
    assert selected >= .9

def test_hash_is_deterministic():
    assert content_hash('same')==content_hash('same')
    assert content_hash('same')!=content_hash('different')

def test_confidence_rule_hides_low_confidence_and_forces_medium_manual_review():
    message={'subject':'Selection update','body':'You have been selected for the role.'}
    low=valid_result();low['confidence']=.65
    validate_result(low,message)
    assert low['status'] == 'IGNORED_LOW_CONFIDENCE'
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

def test_non_iso_offer_dates_are_rejected():
    row=valid_result();row['offer']['joining_date']='12/07/2026'
    with pytest.raises(ValueError,match='invalid ISO date'):
        validate_result(row,{'subject':'Selection update','body':'You have been selected for the role.'})
