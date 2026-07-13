"""Internal notifications for recruitment detections using existing Web Push."""
from __future__ import annotations
import asyncio

NOTIFIABLE={
    'SELECTED','FINAL_SELECTION_CONFIRMED','OFFER_INDICATION','OFFER_IN_PROGRESS',
    'OFFER_APPROVED','OFFER_LETTER_RECEIVED','APPOINTMENT_LETTER_RECEIVED',
    'OFFER_ACCEPTED','JOINING_CONFIRMED','JOINED','POST_SELECTION_ONBOARDING',
    'MANUAL_REVIEW_REQUIRED',
}

def notify_detection(event:dict)->None:
    if event.get('primary_status') not in NOTIFIABLE:return
    if float(event.get('confidence') or 0)<.8:return
    try:
        from features.web_push import admin_usernames_with_subscriptions,send_to_user
        title=event['primary_status'].replace('_',' ').title();body=' · '.join(x for x in [event.get('company_name'),event.get('job_title'),f"{round(float(event.get('confidence') or 0)*100)}% confidence"] if x)
        for user in admin_usernames_with_subscriptions():send_to_user(user,title=title,body=body,tag=f"recruitment:{event['id']}")
    except Exception:pass

def notify_system(title:str,body:str,tag:str)->None:
    try:
        from features.web_push import admin_usernames_with_subscriptions,send_to_user
        for user in admin_usernames_with_subscriptions():send_to_user(user,title=title,body=body,tag=tag)
    except Exception:pass
