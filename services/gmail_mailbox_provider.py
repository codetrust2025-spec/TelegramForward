"""Google Gmail read-only provider using OAuth2 REST APIs."""
from __future__ import annotations
import base64, json, os, urllib.error, urllib.parse, urllib.request
from datetime import datetime, timezone
from email.header import decode_header, make_header
from email.utils import parseaddr, parsedate_to_datetime
from typing import Any
from services.mailbox_provider import MailboxProvider

GMAIL_SCOPE="https://www.googleapis.com/auth/gmail.readonly"

def _secret_key() -> bytes:
    raw=(os.getenv("MAILBOX_CREDENTIAL_ENCRYPTION_KEY") or "").encode()
    if not raw: raise RuntimeError("MAILBOX_CREDENTIAL_ENCRYPTION_KEY is not configured")
    return raw

def encrypt_credentials(value: dict[str,Any]) -> str:
    from cryptography.fernet import Fernet
    return Fernet(_secret_key()).encrypt(json.dumps(value).encode()).decode()

def decrypt_credentials(value: str) -> dict[str,Any]:
    from cryptography.fernet import Fernet
    return json.loads(Fernet(_secret_key()).decrypt(value.encode()).decode())

def authorization_url(state: str, redirect_uri: str) -> str:
    params={"client_id":os.environ["GOOGLE_OAUTH_CLIENT_ID"],"redirect_uri":redirect_uri,"response_type":"code","scope":GMAIL_SCOPE,"access_type":"offline","prompt":"consent","state":state,"include_granted_scopes":"false"}
    return "https://accounts.google.com/o/oauth2/v2/auth?"+urllib.parse.urlencode(params)

def exchange_code(code: str, redirect_uri: str) -> dict[str,Any]:
    data=urllib.parse.urlencode({"code":code,"client_id":os.environ["GOOGLE_OAUTH_CLIENT_ID"],"client_secret":os.environ["GOOGLE_OAUTH_CLIENT_SECRET"],"redirect_uri":redirect_uri,"grant_type":"authorization_code"}).encode()
    with urllib.request.urlopen(urllib.request.Request("https://oauth2.googleapis.com/token",data=data,method="POST"),timeout=20) as r:return json.loads(r.read())

class GmailMailboxProvider(MailboxProvider):
    def __init__(self, credential_ciphertext: str):
        self.credentials=decrypt_credentials(credential_ciphertext); self._status="CONNECTED"; self._cursor=None
    def connect(self)->None:self.verify_connection()
    def disconnect(self)->None:self.credentials={};self._status="DISCONNECTED"
    def get_sync_cursor(self)->str|None:return self._cursor
    def save_sync_cursor(self,cursor:str|None)->None:self._cursor=cursor
    def refresh_connection(self)->None:
        refresh=self.credentials.get("refresh_token")
        if not refresh: raise RuntimeError("Gmail authorization has expired; reconnect the mailbox")
        data=urllib.parse.urlencode({"client_id":os.environ["GOOGLE_OAUTH_CLIENT_ID"],"client_secret":os.environ["GOOGLE_OAUTH_CLIENT_SECRET"],"refresh_token":refresh,"grant_type":"refresh_token"}).encode()
        try:
            with urllib.request.urlopen(urllib.request.Request("https://oauth2.googleapis.com/token",data=data,method="POST"),timeout=20) as r:self.credentials.update(json.loads(r.read()))
        except urllib.error.HTTPError as exc:
            detail=exc.read().decode("utf-8","replace")
            if exc.code==400 and "invalid_grant" in detail:
                raise RuntimeError("Gmail authorization expired or was revoked. Reconnect Gmail to resume automatic monitoring and historical rescans.") from exc
            raise
    def _request(self,path:str,*,method:str="GET",payload:dict[str,Any]|None=None)->dict[str,Any]:
        if not self.credentials.get("access_token"):self.refresh_connection()
        url="https://gmail.googleapis.com/gmail/v1/users/me/"+path
        for attempt in range(2):
            data=json.dumps(payload).encode() if payload is not None else None
            headers={"Authorization":"Bearer "+self.credentials["access_token"]}
            if data is not None:headers["Content-Type"]="application/json"
            req=urllib.request.Request(url,headers=headers,data=data,method=method)
            try:
                with urllib.request.urlopen(req,timeout=30) as r:return json.loads(r.read())
            except urllib.error.HTTPError as exc:
                if exc.code==401 and attempt==0:
                    self.refresh_connection();continue
                self._status="ERROR";raise
            except Exception:
                self._status="ERROR";raise
        raise RuntimeError('Gmail request failed')
    def verify_connection(self)->dict[str,Any]: return self._request("profile")
    def start_watch(self,topic_name:str)->dict[str,Any]:
        """Register/renew Gmail push delivery; Gmail returns historyId + expiration."""
        topic=str(topic_name or "").strip()
        if not topic:raise ValueError("Gmail Pub/Sub topic is required")
        return self._request("watch",method="POST",payload={"topicName":topic,"labelIds":["INBOX"],"labelFilterBehavior":"include"})
    def stop_watch(self)->None:
        self._request("stop",method="POST",payload={})
    def get_connection_status(self)->str:return self._status
    def fetch_new_messages(self,cursor:str|None,*,batch_size:int)->tuple[list[dict[str,Any]],str|None]:
        if cursor:
            try:
                ids=[];page_token=None;latest=str(cursor)
                while len(ids)<batch_size:
                    params={"startHistoryId":cursor,"historyTypes":"messageAdded","maxResults":min(100,batch_size-len(ids))}
                    if page_token:params["pageToken"]=page_token
                    data=self._request("history?"+urllib.parse.urlencode(params))
                    latest=str(data.get("historyId") or latest)
                    for h in data.get("history",[]):
                        ids.extend(x.get("message",{}).get("id") for x in h.get("messagesAdded",[]) if x.get("message",{}).get("id"))
                    page_token=data.get("nextPageToken")
                    if not page_token:break
            except urllib.error.HTTPError as exc:
                # Gmail returns 404 when a history cursor has expired. Recover
                # with the same bounded recent-message scan used on first sync.
                if exc.code!=404:raise
                data=self._request("messages?"+urllib.parse.urlencode({"maxResults":batch_size,"q":"newer_than:30d"}))
                profile=self.verify_connection()
                self._status="CONNECTED"
                return data.get("messages",[]),str(profile.get("historyId") or "")
            return ([{"id":x} for x in dict.fromkeys(ids)][:batch_size],latest)
        data=self._request("messages?"+urllib.parse.urlencode({"maxResults":batch_size,"q":"newer_than:30d"}))
        profile=self.verify_connection(); return data.get("messages",[]),str(profile.get("historyId") or "")
    def fetch_messages_by_date(self,range_start,range_end,*,limit:int=500)->list[dict[str,Any]]:
        # Gmail's `before` boundary is exclusive; include the selected end day.
        from datetime import timedelta
        query=f"after:{range_start:%Y/%m/%d} before:{(range_end+timedelta(days=1)):%Y/%m/%d}"
        messages=[];token=None
        while len(messages)<limit:
            params={"maxResults":min(100,limit-len(messages)),"q":query}
            if token:params["pageToken"]=token
            data=self._request("messages?"+urllib.parse.urlencode(params));messages.extend(data.get("messages",[]));token=data.get("nextPageToken")
            if not token:break
        return messages
    def fetch_message(self,message_id:str)->dict[str,Any]:return self._request(f"messages/{urllib.parse.quote(message_id)}?format=full")
    def fetch_thread(self,thread_id:str)->list[dict[str,Any]]:
        # Full bodies are required for semantic stage progression across a
        # conversation; the read-only Gmail scope still applies.
        return self._request(f"threads/{urllib.parse.quote(thread_id)}?format=full").get("messages",[])
    def fetch_attachments(self,message:dict[str,Any])->list[dict[str,Any]]:
        out=[]
        def walk(part):
            body=part.get("body") or {}; filename=part.get("filename") or ""
            if filename and body.get("attachmentId"):
                raw=self._request(f"messages/{message['id']}/attachments/{body['attachmentId']}")
                data=base64.urlsafe_b64decode((raw.get('data') or '')+'===')
                out.append({"filename":filename,"mime_type":part.get("mimeType"),"size":len(data),"data":data})
            for child in part.get("parts") or []:walk(child)
        walk(message.get("payload") or {});return out

def decode_gmail_message(raw:dict[str,Any],recipient:str)->dict[str,Any]:
    headers={h.get('name','').lower():h.get('value','') for h in raw.get('payload',{}).get('headers',[])}
    def bodies(part):
        found=[];kind=part.get('mimeType');encoded=(part.get('body') or {}).get('data')
        if kind in ('text/plain','text/html') and encoded:
            found.append((kind,base64.urlsafe_b64decode(encoded+'===').decode('utf-8','replace')))
        for child in part.get('parts') or []:found.extend(bodies(child))
        return found
    sender_name,sender_email=parseaddr(headers.get('from','')); sent=None
    try:sent=parsedate_to_datetime(headers.get('date','')).astimezone(timezone.utc)
    except Exception:sent=datetime.now(timezone.utc)
    subject=str(make_header(decode_header(headers.get('subject',''))))
    content=bodies(raw.get('payload') or {});plain='\n'.join(v for k,v in content if k=='text/plain');html_body='\n'.join(v for k,v in content if k=='text/html')
    cc=[address.strip() for address in headers.get('cc','').split(',') if address.strip()]
    return {"provider_message_id":raw['id'],"provider_thread_id":raw.get('threadId'),"sender_name":sender_name,"sender_email":sender_email,"recipient_email":recipient,"cc_metadata":cc,"subject":subject,"sent_at":sent,"body":plain or html_body,"html_body":html_body}
