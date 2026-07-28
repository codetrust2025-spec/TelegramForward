from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from services.calendar_invite_parser import parse_calendar, trusted_interview_result


def invite(*, attendee="reddycharanms@gmail.com", organizer="sakshi@helius-tech.com", tzid="Asia/Kolkata"):
    future = datetime.now(ZoneInfo("Asia/Kolkata")) + timedelta(days=10)
    start = future.replace(hour=17, minute=30, second=0, microsecond=0)
    end = start + timedelta(minutes=30)
    return "\r\n".join([
        "BEGIN:VCALENDAR", "VERSION:2.0", "METHOD:REQUEST", "BEGIN:VEVENT",
        "UID:ram-charan-interview@example", "SEQUENCE:0",
        f"DTSTART;TZID={tzid}:{start:%Y%m%dT%H%M%S}",
        f"DTEND;TZID={tzid}:{end:%Y%m%dT%H%M%S}",
        "SUMMARY:Interview | React/Frontend Developer | Reddy Charan",
        f"ORGANIZER;CN=Sakshi Awasthi:mailto:{organizer}",
        f"ATTENDEE;CN=Reddy Charan:mailto:{attendee}",
        "LOCATION:Microsoft Teams Meeting",
        "DESCRIPTION:Join https://teams.microsoft.com/l/meetup-join/room",
        "END:VEVENT", "END:VCALENDAR", "",
    ])


def decoded(**changes):
    value = {
        "sender_name": "Sakshi Awasthi", "sender_email": "sakshi@helius-tech.com",
        "recipient_email": "reddycharanms@gmail.com",
        "subject": "Interview | React/Frontend Developer | Reddy Charan",
        "authentication_results": "mx.google.com; spf=pass smtp.mailfrom=helius-tech.com; dmarc=none header.from=helius-tech.com",
        "received_spf": "pass (google.com: domain of sakshi@helius-tech.com designates 1.2.3.4 as permitted sender)",
    }
    value.update(changes)
    return value


def attachment(text=None):
    return [{"filename": "invite.ics", "mime_type": "text/calendar", "text": text or invite()}]


def test_parses_timezone_bearing_calendar_invite():
    value = parse_calendar(invite())
    assert value["uid"] == "ram-charan-interview@example"
    assert value["start"].strftime("%I:%M %p") == "05:30 PM"
    assert value["timezone"] == "Asia/Kolkata"
    assert value["meeting_link"].startswith("https://teams.microsoft.com/")


def test_windows_outlook_timezone_is_mapped_to_iana():
    value = parse_calendar(invite(tzid="Singapore Standard Time"))
    assert value["timezone"] == "Asia/Singapore"


def test_exchange_z_timezone_is_explicit_utc():
    value = parse_calendar(invite(tzid="Z"))
    assert value["timezone"] == "UTC"


def test_authenticated_matching_invite_bypasses_ollama_safely():
    result = trusted_interview_result(decoded(), attachment())
    assert result["classification"] == "interview_confirmed"
    assert result["classification_source"] == "ICALENDAR_VERIFIED"
    assert result["calendar_validation_status"] == "TRUSTED"
    assert result["interview"]["time"] == "05:30 PM"
    assert result["interview"]["round"] is None


def test_authenticated_enterprise_sender_can_name_same_domain_organizer():
    value = decoded(
        sender_email="talent-acquisition@infosys.com",
        recipient_email="sakthivelthangaraj04@gmail.com",
        subject="Interview Invite: Sakthivel | Candidate ID: 1010934472",
        authentication_results=(
            "dkim=pass header.i=@infosys.com header.d=infosys.com; "
            "dmarc=pass header.from=infosys.com"
        ),
        received_spf="pass domain of infosys.com permitted sender",
    )
    text = invite(
        attendee="sakthivelthangaraj04@gmail.com",
        organizer="pallavi33@infosys.com",
        tzid="Z",
    )

    result = trusted_interview_result(value, attachment(text))

    assert result["classification"] == "interview_confirmed"
    assert result["classification_source"] == "ICALENDAR_VERIFIED"
    assert result["interview"]["timezone"] == "UTC"
    assert result["interview"]["round"] is None


def test_calendar_round_is_extracted_only_when_explicit():
    text = invite().replace(
        "SUMMARY:Interview | React/Frontend Developer | Reddy Charan",
        "SUMMARY:L2 Interview | React/Frontend Developer | Reddy Charan",
    )

    result = trusted_interview_result(
        decoded(subject="L2 Interview | React/Frontend Developer | Reddy Charan"),
        attachment(text),
    )

    assert result["interview"]["round"] == "L2"


def test_cross_domain_calendar_organizer_is_not_trusted():
    value = decoded(
        sender_email="talent-acquisition@infosys.com",
        authentication_results=(
            "dkim=pass header.i=@infosys.com header.d=infosys.com; "
            "dmarc=pass header.from=infosys.com"
        ),
        received_spf="pass domain of infosys.com permitted sender",
    )
    assert trusted_interview_result(
        value,
        attachment(invite(organizer="recruiter@attacker.invalid")),
    ) is None


def test_spoofed_or_unaligned_sender_is_not_trusted():
    assert trusted_interview_result(
        decoded(authentication_results="spf=fail smtp.mailfrom=attacker.invalid", received_spf="fail"), attachment()
    ) is None
    assert trusted_interview_result(decoded(sender_email="attacker@example.invalid"), attachment()) is None


def test_wrong_candidate_attendee_is_not_trusted():
    assert trusted_interview_result(decoded(), attachment(invite(attendee="someoneelse@gmail.com"))) is None


def test_floating_calendar_time_is_not_trusted_for_booking():
    text = invite().replace("DTSTART;TZID=Asia/Kolkata:", "DTSTART:").replace("DTEND;TZID=Asia/Kolkata:", "DTEND:")
    assert trusted_interview_result(decoded(), attachment(text)) is None


def test_authenticated_tcs_plain_text_invite_uses_configured_domain_timezone(monkeypatch):
    future = datetime.now(ZoneInfo("Asia/Kolkata")) + timedelta(days=10)
    body = f"""Greetings from TATA Consultancy Services
We are delighted to invite you for a discussion. The interview will be video based using MS Teams.
Interview Details:
Date: {future:%d}th {future:%B%y}
Time: 2:30 PM - 3 PM
Link to join: https://teams.microsoft.com/meet/416486720484824
Mandatory checklist: Experience Letter/Relieving Letter/Appointment Letter of all your previous companies.
"""
    value=decoded(
        sender_email='shreya.ghosh9@tcs.com',recipient_email='wasanthi.adapa@gmail.com',
        subject=f'TCS Interview_ {future:%d}th {future:%B%y}',body=body,
        message_direction='INBOUND',to_metadata=['wasanthi.adapa@gmail.com'],
        authentication_results='dkim=none; dmarc=none header.from=tcs.com',
        received_spf='pass domain of shreya.ghosh9@tcs.com permitted sender',
    )
    monkeypatch.setenv('AI_INTERVIEW_DEFAULT_TIMEZONE','Asia/Kolkata')
    monkeypatch.setenv('AI_INTERVIEW_DEFAULT_TIMEZONE_DOMAINS','tcs.com')
    result=trusted_interview_result(value,[])
    assert result['classification']=='interview_confirmed'
    assert result['classification_source']=='STRUCTURED_EMAIL_VERIFIED'
    assert result['timezone_source']=='DOMAIN_POLICY'
    assert result['offer']['appointment_letter_detected'] is False


def test_plain_text_invite_rejects_outbound_and_unconfigured_timezone(monkeypatch):
    future = datetime.now(ZoneInfo("Asia/Kolkata")) + timedelta(days=10)
    body=f'Interview Details Date: {future:%d}th {future:%B%y} Time: 2:30 PM Please join https://teams.microsoft.com/meet/room'
    value=decoded(sender_email='hr@company.test',recipient_email='candidate@test.invalid',body=body,
                  subject='Interview invitation',to_metadata=['candidate@test.invalid'],message_direction='INBOUND',
                  received_spf='pass domain of hr@company.test permitted sender')
    monkeypatch.delenv('AI_INTERVIEW_DEFAULT_TIMEZONE',raising=False)
    monkeypatch.delenv('AI_INTERVIEW_DEFAULT_TIMEZONE_DOMAINS',raising=False)
    assert trusted_interview_result(value,[]) is None


def test_authenticated_numeric_date_interview_invite_is_tracked_without_ai():
    value = decoded(
        sender_email='talent-acquisition@infosys.com',
        recipient_email='sakthivelthangaraj04@gmail.com',
        subject='Interview Invite: Sakthivel | Candidate ID: 1010934472',
        body=(
            'Interview Invite: Sakthivel\n'
            'Meeting Date and Time: 25-07-2026 10:30 IST\n'
            'Interview Link: https://teams.microsoft.com/l/meetup-join/example'
        ),
        message_direction='INBOUND',
        to_metadata=['sakthivelthangaraj04@gmail.com'],
        authentication_results='spf=pass smtp.mailfrom=infosys.com; dmarc=pass header.from=infosys.com',
        received_spf='pass domain of infosys.com permitted sender',
    )

    result = trusted_interview_result(value, [])

    assert result['classification'] == 'interview_confirmed'
    assert result['classification_source'] == 'STRUCTURED_EMAIL_VERIFIED'
    assert result['interview']['date'] == '2026-07-25'
    assert result['interview']['time'] == '10:30 AM'
    assert result['interview']['timezone'] == 'Asia/Kolkata'
    assert result['interview']['round'] is None


def test_plain_text_invite_delivered_through_an_alias_is_tracked():
    value = decoded(
        sender_email='talent-acquisition@infosys.com',
        recipient_email='sakthivelthangaraj04@gmail.com',
        subject='Interview Invite: Sakthivel',
        body=(
            'Interview Invite\nMeeting Date and Time: 25-07-2026 10:30 IST\n'
            'Interview Link: https://teams.microsoft.com/l/meetup-join/example'
        ),
        message_direction='INBOUND',
        # The visible header can name an alias or forwarding address instead
        # of the mailbox that received and authenticated the message.
        to_metadata=['pallavi33@infosys.com'],
        authentication_results='spf=pass smtp.mailfrom=infosys.com; dmarc=pass header.from=infosys.com',
        received_spf='pass domain of infosys.com permitted sender',
    )

    assert trusted_interview_result(value, [])['classification'] == 'interview_confirmed'


def test_authenticated_cancelled_enterprise_event_bypasses_ollama_safely():
    value = decoded(
        sender_name="M, Maneesh",
        sender_email="maneesh.m.ext@capgemini.com",
        recipient_email="reddycharanms@gmail.com",
        subject="Canceled: L1-CGEMJP00347400-React UI Developer-Reddy Charan M S",
        body=(
            "Your profile has been shortlisted for Capgemini L1 round. "
            "We would like to schedule your interview."
        ),
        message_direction="INBOUND",
        authentication_results=(
            "dkim=pass header.i=@capgemini.com header.d=capgemini.com; "
            "dmarc=pass header.from=capgemini.com"
        ),
        received_spf="pass domain of capgemini.com permitted sender",
    )

    result = trusted_interview_result(value, [])

    assert result["classification"] == "interview_cancelled"
    assert result["classification_source"] == "STRUCTURED_EMAIL_VERIFIED"
    assert result["structured_validation_status"] == "TRUSTED"
    assert result["interview"]["round"] == "L1"
    assert result["interview"]["stable_ids"] == ["CGEMJP00347400"]
    assert result["requires_manual_review"] is False


def test_cancelled_subject_is_not_trusted_without_sender_authentication():
    value = decoded(
        subject="Canceled: L1-CGEMJP00347400-React UI Developer-Reddy Charan M S",
        body="The interview has been cancelled.",
        authentication_results="spf=fail; dkim=fail; dmarc=fail",
        received_spf="fail",
    )

    assert trusted_interview_result(value, []) is None
