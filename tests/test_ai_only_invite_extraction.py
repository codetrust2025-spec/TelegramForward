"""AI-only mode must not be gated on an OCR cross-check.

When the admin turns the global OCR switch off, Tesseract is forbidden to run
anywhere. The invite extractor still demanded that OCR independently confirm
the date and start time, so every booking was blocked with
"OCR did not independently extract a supported date and start time" — an
impossible bar and a message about a component that was not even allowed to run.
"""

from __future__ import annotations

import pytest

from features import ollama_invite_extract as oie


VISION_JSON = {
    "candidate_name": "Abilash Perla",
    "interview_date": "2026-08-10",
    "start_time": "02:30 PM",
    "end_time": "03:30 PM",
    "interview_round": "L2",
    "technology": "Test Automation",
    "meeting_platform": "Microsoft Teams",
    "timezone": "IST",
    "looks_like_interview_invite": True,
}


@pytest.fixture()
def ai_only(monkeypatch):
    """Global OCR off, Ollama reachable, vision returns a complete invite."""
    monkeypatch.setattr(oie, "processing_mode", lambda: "ai")
    monkeypatch.setattr(oie, "ocr_enabled", lambda: False)
    monkeypatch.setattr(oie, "_is_ollama_available", lambda: True)
    monkeypatch.setattr(oie, "_ollama_only_test_mode", lambda: False)
    monkeypatch.setattr(oie, "_get_invite_prompt", lambda: "prompt")
    monkeypatch.setattr(oie, "call_ollama_vision_model", lambda *a, **k: "{}")
    monkeypatch.setattr(oie, "parse_strict_json_response", lambda _r: dict(VISION_JSON))


@pytest.fixture()
def ocr_forbidden(monkeypatch):
    """Any OCR call in AI-only mode is a hard failure, not a soft warning."""
    calls: list[str] = []

    def _boom(*_a, **_k):
        calls.append("ocr")
        raise AssertionError("OCR must never run while the global switch is off")

    monkeypatch.setattr(oie, "_run_tesseract_ocr", _boom)
    monkeypatch.setattr(oie, "_fallback_to_existing_ocr", _boom)
    monkeypatch.setattr(oie, "_try_text_model_cleanup", _boom)
    return calls


def test_ai_only_success_is_not_blocked_by_missing_ocr(ai_only, ocr_forbidden):
    result = oie.extract_interview_invite_with_ollama(b"image-bytes", "image/png")

    assert result["auto_booking_safe"] is True
    assert result["manual_fields_required"] is False
    assert result["interview_date"] == "2026-08-10"
    assert result["start_time"] == "02:30 PM"
    assert not result.get("failure_reason")


def test_ai_only_never_calls_any_ocr_function(ai_only, ocr_forbidden):
    oie.extract_interview_invite_with_ollama(b"image-bytes", "image/png")

    assert ocr_forbidden == []


def test_ai_only_never_shows_an_ocr_error(ai_only, ocr_forbidden, monkeypatch):
    """Even when the AI fails, the operator is never told OCR let them down."""
    monkeypatch.setattr(oie, "call_ollama_vision_model", lambda *a, **k: None)
    monkeypatch.setattr(oie, "parse_strict_json_response", lambda _r: None)

    result = oie.extract_interview_invite_with_ollama(b"image-bytes", "image/png")

    assert result["manual_fields_required"] is True
    blob = " ".join(
        [str(result.get("failure_reason") or ""), *[str(w) for w in result.get("warnings") or []]]
    )
    assert "OCR" not in blob
    assert "AI" in blob


def test_ai_only_reports_its_mode_and_that_ocr_was_not_used(ai_only, ocr_forbidden):
    result = oie.extract_interview_invite_with_ollama(b"image-bytes", "image/png")

    assert result["processing_mode"] == "ai"
    assert result["ocr_used"] is False
    assert result["extraction_method"] == "ai_only"


def test_ai_only_incomplete_data_allows_manual_confirmation(ai_only, ocr_forbidden, monkeypatch):
    partial = {**VISION_JSON, "start_time": ""}
    monkeypatch.setattr(oie, "parse_strict_json_response", lambda _r: dict(partial))

    result = oie.extract_interview_invite_with_ollama(b"image-bytes", "image/png")

    assert result["auto_booking_safe"] is False
    assert result["manual_fields_required"] is True
    assert result["failure_stage"] == "ai_incomplete"
    assert "start time" in result["failure_reason"]
    assert "OCR" not in result["failure_reason"]
    # The date the AI did read is still offered, so the operator only fills the gap.
    assert result["interview_date"] == "2026-08-10"


def test_ai_only_handles_an_unreachable_model_without_mentioning_ocr(
    ai_only, ocr_forbidden, monkeypatch
):
    monkeypatch.setattr(oie, "_is_ollama_available", lambda: False)

    result = oie.extract_interview_invite_with_ollama(b"image-bytes", "image/png")

    assert result["manual_fields_required"] is True
    assert result["failure_stage"] == "ollama_unavailable"
    assert "OCR" not in str(result.get("warnings"))
    assert ocr_forbidden == []


def test_mode_is_snapshotted_once_per_request(monkeypatch, ocr_forbidden):
    """A switch flipped mid-extraction must not split a run across modes."""
    seen = []

    def _flipping_mode():
        seen.append(len(seen))
        return "ai" if len(seen) == 1 else "ocr+ai"

    monkeypatch.setattr(oie, "processing_mode", _flipping_mode)
    monkeypatch.setattr(oie, "_is_ollama_available", lambda: True)
    monkeypatch.setattr(oie, "_ollama_only_test_mode", lambda: False)
    monkeypatch.setattr(oie, "_get_invite_prompt", lambda: "prompt")
    monkeypatch.setattr(oie, "call_ollama_vision_model", lambda *a, **k: "{}")
    monkeypatch.setattr(oie, "parse_strict_json_response", lambda _r: dict(VISION_JSON))

    result = oie.extract_interview_invite_with_ollama(b"image-bytes", "image/png")

    assert result["processing_mode"] == "ai"
    assert result["ocr_used"] is False


# ── OCR + AI mode keeps its existing safety behaviour ────────────────────────

@pytest.fixture()
def ocr_and_ai(monkeypatch):
    monkeypatch.setattr(oie, "processing_mode", lambda: "ocr+ai")
    monkeypatch.setattr(oie, "ocr_enabled", lambda: True)
    monkeypatch.setattr(oie, "_is_ollama_available", lambda: True)
    monkeypatch.setattr(oie, "_ollama_only_test_mode", lambda: False)
    monkeypatch.setattr(oie, "_get_invite_prompt", lambda: "prompt")
    monkeypatch.setattr(oie, "call_ollama_vision_model", lambda *a, **k: "{}")
    monkeypatch.setattr(oie, "parse_strict_json_response", lambda _r: dict(VISION_JSON))


def test_ocr_and_ai_still_blocks_when_the_two_sources_conflict(ocr_and_ai, monkeypatch):
    conflicting = "Date: 11 August 2026\nTime: 04:00 PM IST\n"
    monkeypatch.setattr(oie, "_run_tesseract_ocr", lambda _d: conflicting)
    monkeypatch.setattr(
        oie,
        "_try_text_model_cleanup",
        lambda _t: {
            "interview_date": "2026-08-11",
            "start_time": "04:00 PM",
            "timezone": "IST",
            "looks_like_interview_invite": True,
        },
    )

    result = oie.extract_interview_invite_with_ollama(b"image-bytes", "image/png")

    assert result["auto_booking_safe"] is False
    assert result["manual_fields_required"] is True
    assert result["processing_mode"] == "ocr+ai"
    assert result["ocr_used"] is True


def test_ocr_and_ai_still_blocks_when_ocr_finds_nothing(ocr_and_ai, monkeypatch):
    """The pre-existing fail-closed behaviour is unchanged when OCR is on."""
    monkeypatch.setattr(oie, "_run_tesseract_ocr", lambda _d: "")

    result = oie.extract_interview_invite_with_ollama(b"image-bytes", "image/png")

    assert result["auto_booking_safe"] is False
    assert result["processing_mode"] == "ocr+ai"
    assert "OCR" in str(result.get("failure_reason") or "")
