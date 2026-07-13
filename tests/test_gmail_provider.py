import base64
from cryptography.fernet import Fernet
from services.gmail_mailbox_provider import decode_gmail_message,encrypt_credentials,decrypt_credentials

def test_credentials_are_encrypted(monkeypatch):
    monkeypatch.setenv('MAILBOX_CREDENTIAL_ENCRYPTION_KEY',Fernet.generate_key().decode())
    fake_value='unit'+'-test-value'
    cipher=encrypt_credentials({'refresh_token':fake_value})
    assert fake_value not in cipher
    assert decrypt_credentials(cipher)['refresh_token']==fake_value

def test_decode_gmail_message():
    sender='jobs'+'@'+'test.invalid';recipient='candidate'+'@'+'test.invalid'
    body=base64.urlsafe_b64encode(b'Your interview is scheduled.').decode().rstrip('=')
    raw={'id':'m1','threadId':'t1','payload':{'headers':[{'name':'From','value':f'Recruiter <{sender}>'},{'name':'Subject','value':'Interview scheduled'},{'name':'Date','value':'Sun, 12 Jul 2026 13:00:00 +0530'}],'mimeType':'text/plain','body':{'data':body}}}
    row=decode_gmail_message(raw,recipient)
    assert row['provider_message_id']=='m1'
    assert row['sender_email']==sender
    assert 'interview is scheduled' in row['body']

def test_decode_uses_html_when_plain_text_is_missing():
    encoded=base64.urlsafe_b64encode(b'<p>Interview <strong>confirmed</strong></p>').decode().rstrip('=')
    raw={'id':'m2','payload':{'headers':[{'name':'From','value':'Recruiter'},{'name':'Cc','value':'first@test.invalid, second@test.invalid'}],'mimeType':'text/html','body':{'data':encoded}}}
    row=decode_gmail_message(raw,'candidate'+'@'+'test.invalid')
    assert 'Interview' in row['body']
    assert len(row['cc_metadata'])==2
