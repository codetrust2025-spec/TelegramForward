from workers.recruitment_mail_worker import RecruitmentMailWorker
import urllib.error

class FakeProvider:
    def __init__(self,_):pass
    def fetch_new_messages(self,cursor,*,batch_size):return ([{'id':'m1'}],'history-2')
    def fetch_message(self,message_id):return {'id':message_id,'threadId':'t1','payload':{'headers':[],'body':{}}}
    def fetch_attachments(self,message):return []
    def fetch_messages_by_date(self,start,end,*,limit=500):return [{'id':'m1'}]

def test_worker_completes_incremental_job(monkeypatch):
    import workers.recruitment_mail_worker as module
    mailbox={'id':'mb1','candidate_id':'c1','email_address':'candidate'+'@'+'test.invalid','credential_ciphertext':'encrypted','provider_history_id':'history-1','failed_sync_count':0}
    updates=[];finished=[]
    monkeypatch.setattr(module.store,'mailbox_by_id',lambda _:mailbox)
    monkeypatch.setattr(module.store,'update_mailbox',lambda mid,values:updates.append(values) or mailbox)
    monkeypatch.setattr(module.store,'finish_job',lambda jid,**values:finished.append(values))
    monkeypatch.setattr(module,'GmailMailboxProvider',FakeProvider)
    monkeypatch.setattr(module,'decode_gmail_message',lambda raw,email:{'provider_message_id':'m1','provider_thread_id':'t1','sender_email':'jobs'+'@'+'test.invalid','recipient_email':email,'subject':'Interview','sent_at':None,'body':'Scheduled'})
    monkeypatch.setattr(module,'process_message',lambda mailbox,message,attachments:{'id':'event1'})
    RecruitmentMailWorker().process_job({'id':'j1','mailbox_id':'mb1','attempts':1})
    assert finished[-1]['status']=='COMPLETED'
    assert finished[-1]['counts']=={'fetched':1,'processed':1,'events':1}
    assert any(v.get('provider_history_id')=='history-2' for v in updates)


def test_worker_reprocesses_historical_messages_without_duplicate_download(monkeypatch):
    import workers.recruitment_mail_worker as module
    mailbox={'id':'mb1','candidate_id':'c1','email_address':'candidate@test.invalid','credential_ciphertext':'encrypted','provider_history_id':'history-1','failed_sync_count':0}
    finished=[];calls=[]
    monkeypatch.setattr(module.store,'mailbox_by_id',lambda _:mailbox)
    monkeypatch.setattr(module.store,'update_mailbox',lambda mid,values:mailbox)
    monkeypatch.setattr(module.store,'finish_job',lambda jid,**values:finished.append(values))
    monkeypatch.setattr(module.store,'stored_message',lambda *args:{'id':'stored','provider_message_id':'m1','provider_thread_id':None,'sender_name':'HR','sender_email':'hr@test.invalid','recipient_email':'candidate@test.invalid','subject':'Joining','sent_at':None,'body_text':'Your joining date is 15 July 2026.','html_body_text':'','processing_status':'IGNORED_NOT_OFFER_RELATED'})
    monkeypatch.setattr(module.store,'attachments_for_message',lambda *args,**kwargs:[])
    monkeypatch.setattr(module,'GmailMailboxProvider',FakeProvider)
    monkeypatch.setattr(module,'process_message',lambda mailbox,message,attachments,**kwargs:calls.append(kwargs) or {'id':'event1'})
    RecruitmentMailWorker().process_job({'id':'j2','mailbox_id':'mb1','attempts':1,'job_type':'HISTORICAL_RESCAN','range_start':__import__('datetime').date(2026,7,1),'range_end':__import__('datetime').date(2026,7,14)})
    assert calls == [{'reprocess':True}]
    assert finished[-1]['status']=='COMPLETED'
    assert finished[-1]['counts']=={'fetched':1,'processed':1,'events':1}


def test_worker_skips_deleted_gmail_message_instead_of_failing_batch(monkeypatch):
    import workers.recruitment_mail_worker as module
    class DeletedProvider(FakeProvider):
        def fetch_message(self,message_id):raise urllib.error.HTTPError('gmail',404,'deleted',{},None)
    mailbox={'id':'mb1','candidate_id':'c1','email_address':'candidate@test.invalid','credential_ciphertext':'encrypted','provider_history_id':'history-1','failed_sync_count':0}
    finished=[]
    monkeypatch.setattr(module.store,'mailbox_by_id',lambda _:mailbox)
    monkeypatch.setattr(module.store,'update_mailbox',lambda mid,values:mailbox)
    monkeypatch.setattr(module.store,'finish_job',lambda jid,**values:finished.append(values))
    monkeypatch.setattr(module,'GmailMailboxProvider',DeletedProvider)
    RecruitmentMailWorker().process_job({'id':'j3','mailbox_id':'mb1','attempts':1})
    assert finished[-1]['status']=='COMPLETED'
    assert finished[-1]['counts']=={'fetched':1,'processed':0,'events':0}
