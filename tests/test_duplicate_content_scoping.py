"""Two different interviews from one recruiter must not dedupe each other.

Built from the real incident: Sourcebae booked Pujitha twice from the same
template. Both covering mails had byte-identical bodies — the substance was in
the subject and the invitation — so they shared body hash b039d324…. The second
interview (11 Aug, 4:15pm) was marked DUPLICATE_CONTENT and never reached the
booking validator, while the first (10:30am) had been processed normally.

Nothing appeared on any screen, because dropping a message writes a
processing_status and returns; it creates no notification.
"""
from __future__ import annotations

import pytest

from core import recruitment_mail_store as store
from services import recruitment_mail_agent as agent


class FakeCursor:
    """Records the SQL and answers with whatever the test seeded."""

    def __init__(self, rows):
        self._rows = rows
        self.executed = []

    def execute(self, sql, params=None):
        self.executed.append((" ".join(sql.split()), params))

    def fetchone(self):
        return self._rows.pop(0) if self._rows else None

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


class FakeConn:
    def __init__(self, cursor):
        self._cursor = cursor

    def cursor(self):
        return self._cursor

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


@pytest.fixture
def captured(monkeypatch):
    cursor = FakeCursor(rows=[])

    def fake_connection():
        return FakeConn(cursor)

    monkeypatch.setattr(store, "get_connection", fake_connection)
    return cursor


# The two real covering mails: same body, different interview.
SAME_BODY = "b039d324ab104b9424e0350d300c778d9d96549b"
FIRST_SUBJECT = "Fullstack Gen Ai Role || Shethink Sourcebae"
SECOND_SUBJECT = "Fullstack Ai || Shethink Sourcebae"


def test_the_subject_is_part_of_a_body_hash_duplicate(captured):
    """A body match alone must no longer be enough to call it a duplicate."""
    store.is_duplicate_content("cand-1", "msg-2", "hash-b", SAME_BODY, SECOND_SUBJECT)

    sql, params = captured.executed[-1]
    assert "m.body_hash=%s" in sql
    assert "COALESCE(m.subject,'')=COALESCE(%s,'')" in sql, (
        "body-hash dedupe must also compare the subject"
    )
    assert SECOND_SUBJECT in params


def test_message_hash_dedupe_is_left_alone(captured):
    """The exact-resend test must keep working exactly as before."""
    store.is_duplicate_content("cand-1", "msg-2", "hash-b", SAME_BODY, SECOND_SUBJECT)

    sql, params = captured.executed[-1]
    assert "m.message_hash=%s" in sql
    # message_hash is still tested on its own, un-conditioned by the subject.
    before_or = sql.split("OR")[0]
    assert "m.message_hash=%s" in before_or
    assert "subject" not in before_or


def test_an_identical_resend_is_still_a_duplicate(captured):
    """Same subject and same body — a genuine resend — must still be caught."""
    captured._rows = [(1,)]
    assert store.is_duplicate_content("cand-1", "msg-2", "hash-b", SAME_BODY, FIRST_SUBJECT) is True


def test_the_second_sourcebae_interview_is_not_a_duplicate(captured):
    """The regression itself: no matching row, so it proceeds to classification."""
    captured._rows = []
    assert store.is_duplicate_content("cand-1", "msg-2", "hash-b", SAME_BODY, SECOND_SUBJECT) is False


def test_an_empty_body_never_dedupes_on_body_alone(captured):
    """Pre-existing guard: an empty body is not evidence of anything."""
    store.is_duplicate_content("cand-1", "msg-2", "hash-b", store.content_hash_empty(), "Any")
    sql, params = captured.executed[-1]
    assert store.content_hash_empty() in params


# ── a dropped interview must leave a trace ───────────────────────────────────


def test_a_dropped_interview_mail_is_announced(monkeypatch):
    published = []
    monkeypatch.setattr(agent, "_publish", lambda event, **kw: published.append((event, kw)))
    monkeypatch.setattr(
        "services.calendar_invite_parser.trusted_interview_result",
        lambda decoded, attachments: {
            "interview_date": "2026-08-11",
            "interview_time": "16:15",
        },
    )

    signal = agent._publish_ignored_interview(
        {"candidate_id": "9317567fd2"},
        {"subject": SECOND_SUBJECT, "provider_message_id": "gmail-1"},
        [],
        "DUPLICATE_CONTENT",
        "DUPLICATE_MESSAGE",
    )

    assert signal is not None
    assert published, "an interview dropped before classification must be surfaced"
    event, payload = published[-1]
    assert event == "interview_mail_ignored"
    assert payload["candidate_id"] == "9317567fd2"
    assert payload["processing_status"] == "DUPLICATE_CONTENT"
    assert payload["reason"] == "DUPLICATE_MESSAGE"
    assert payload["interview_date"] == "2026-08-11"
    assert payload["interview_time"] == "16:15"


def test_ordinary_filtered_mail_does_not_become_operator_noise(monkeypatch):
    published = []
    monkeypatch.setattr(agent, "_publish", lambda event, **kw: published.append((event, kw)))
    monkeypatch.setattr(
        "services.calendar_invite_parser.trusted_interview_result",
        lambda decoded, attachments: None,
    )

    signal = agent._publish_ignored_interview(
        {"candidate_id": "c1"},
        {"subject": "Job | Fullstack Developer in Bengaluru"},
        [],
        "IGNORED_NOT_OFFER_RELATED",
        "JOB_PORTAL_MARKETING",
    )

    assert signal is None
    assert published == []


def test_a_broken_parser_cannot_break_ingestion(monkeypatch):
    monkeypatch.setattr(agent, "_publish", lambda event, **kw: None)

    def explode(decoded, attachments):
        raise RuntimeError("parser is down")

    monkeypatch.setattr("services.calendar_invite_parser.trusted_interview_result", explode)
    assert agent._publish_ignored_interview({"candidate_id": "c1"}, {}, [], "X", "Y") is None
