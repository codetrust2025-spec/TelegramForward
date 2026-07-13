from services.recruitment_mail_agent import clean_email, relevance_score, content_hash, validate_result, parse_model_json

def valid_result():
    return {'schema_version':'recruitment_event_v1','is_recruitment_related':True,'primary_status':'SHORTLISTED','confidence':.9,'candidate':{'name':None,'email':None},'company':{'name':None,'domain':None},'job':{'title':None,'employment_type':None,'location':None},'recruiter':{'name':None,'email':None},'interview':{k:None for k in ['date','time','timezone','mode','round','location','meeting_link']},'offer':{'offer_detected':False,'offer_letter_detected':False,'offer_date':None,'offered_ctc':None,'currency':None,'joining_date':None,'offer_expiry_date':None},'attachments':[],'evidence':[],'risk_flags':[],'requires_manual_review':False,'summary':'Shortlisted.','recommended_action':'Review.'}

def test_clean_email_removes_html_and_quoted_history():
    value=clean_email('<p>Your interview has been scheduled.</p>\nOn yesterday Recruiter wrote:\nold text')
    assert value=='Your interview has been scheduled.'

def test_recruitment_filter_scores_invite_but_not_job_alert():
    invite=relevance_score('Interview scheduled','Your technical round is confirmed.',['invite.pdf'])
    alert=relevance_score('LinkedIn job alert','New jobs selected for you',[])
    assert invite >= .55
    assert alert < invite

def test_recruitment_filter_uses_thread_context():
    score=relevance_score('Re: update','Please see below.',[],[{'subject':'Technical round interview confirmation'}])
    assert score > 0

def test_hash_is_deterministic():
    assert content_hash('same')==content_hash('same')
    assert content_hash('same')!=content_hash('different')

def test_confidence_rule_forces_manual_review():
    row=valid_result();row['confidence']=.65
    validate_result(row)
    assert row['requires_manual_review'] is True

def test_invalid_status_is_rejected():
    row=valid_result();row['primary_status']='MADE_UP'
    try:validate_result(row)
    except ValueError:return
    raise AssertionError('invalid status accepted')

def test_safe_json_repair_once():
    assert parse_model_json('```json\n{"status":"ok",}\n```') == {'status':'ok'}

def test_non_iso_dates_and_times_are_rejected():
    row=valid_result();row['interview']['date']='12/07/2026'
    try:validate_result(row)
    except ValueError:pass
    else:raise AssertionError('non-ISO date accepted')
    row=valid_result();row['interview']['time']='1:30 PM'
    try:validate_result(row)
    except ValueError:return
    raise AssertionError('non-ISO time accepted')
