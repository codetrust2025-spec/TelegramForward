"""Invite extraction must always answer with JSON, never let the proxy answer.

Nginx gives the app 300s (proxy_read_timeout) before serving its own HTML 504
page. The extractor's OLLAMA_TIMEOUT defaults to 900s, so without an
application deadline a slow model let Nginx reply first and the browser tried
to parse "<html>..." as JSON.
"""
from __future__ import annotations

import pytest

from core import public_slot_api as api

NGINX_PROXY_READ_TIMEOUT = 300


def test_default_timeout_is_ninety_seconds(monkeypatch):
    monkeypatch.delenv("INVITE_EXTRACTION_TIMEOUT", raising=False)
    assert api.invite_extraction_timeout_seconds() == 90


def test_timeout_is_configurable(monkeypatch):
    monkeypatch.setenv("INVITE_EXTRACTION_TIMEOUT", "120")
    assert api.invite_extraction_timeout_seconds() == 120


@pytest.mark.parametrize("value", ["9999", "301", "100000"])
def test_timeout_is_clamped_below_the_proxy_timeout(monkeypatch, value):
    monkeypatch.setenv("INVITE_EXTRACTION_TIMEOUT", value)
    resolved = api.invite_extraction_timeout_seconds()
    assert resolved <= api.INVITE_EXTRACTION_TIMEOUT_CEILING
    # The whole point: the application must answer before the proxy does.
    assert resolved < NGINX_PROXY_READ_TIMEOUT


@pytest.mark.parametrize("value", ["", "abc", "0", "-5", "  "])
def test_invalid_timeout_falls_back_to_the_default(monkeypatch, value):
    monkeypatch.setenv("INVITE_EXTRACTION_TIMEOUT", value)
    assert api.invite_extraction_timeout_seconds() == 90


def test_fallback_payload_is_sanitized_and_requires_manual_entry():
    payload = api._invite_extraction_fallback("Invite reading took too long.")

    assert payload["status"] == "ok"
    assert payload["success"] is False
    assert payload["extraction_source"] == "error"

    data = payload["data"]
    assert data["manual_fields_required"] is True
    assert data["confidence_score"] == 0
    # No booking-usable values may be invented on the failure path.
    assert data["interview_date"] == ""
    assert data["start_time"] == ""
    assert data["interview_round"] == ""
    assert set(data["missing_fields"]) == {
        "interview_date",
        "start_time",
        "interview_round",
    }


def test_fallback_never_leaks_html_or_parser_noise():
    payload = api._invite_extraction_fallback("Invite reading took too long.")
    blob = repr(payload).lower()
    for leaked in ("<html>", "unexpected token", "traceback", "gateway time-out"):
        assert leaked not in blob


def test_timeout_fallback_creates_no_candidate_and_no_booking(monkeypatch, tmp_path):
    """The failure path is pure: it must not touch the candidate store."""
    from features import candidate_store as cs

    monkeypatch.setattr(cs, "_FILE", str(tmp_path / "candidates.json"), raising=False)
    monkeypatch.setattr(cs, "_CACHE", None, raising=False)
    cs._save({"candidates": []})
    before = len(cs._load(force=True).get("candidates") or [])

    payload = api._invite_extraction_fallback("Invite reading took too long.")

    after = len(cs._load(force=True).get("candidates") or [])
    assert after == before == 0
    assert payload["data"]["manual_fields_required"] is True
