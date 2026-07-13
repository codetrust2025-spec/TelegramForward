from workers.recruitment_mail_worker import RecruitmentMailWorker

class FakeProvider:
    def __init__(self,_):pass
    def fetch_new_messages(self,cursor,*,batch_size):return ([{'id':'m1'}],'history-2')
    def fetch_message(self,message_id):return {'id':message_id,'threadId':'t1','payload':{'headers':[],'body':{}}}
    def fetch_attachments(self,message):return []

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
