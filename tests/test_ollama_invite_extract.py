import json

import features.ollama_invite_extract as invite_extract

from features.ollama_invite_extract import (
    INVITE_EXTRACTION_PROMPT,
    _date_time_agree,
    _ollama_only_test_mode,
    normalize_time_to_12h,
    validate_12h_time_format,
)


def test_normalizes_malformed_24_hour_with_pm_suffix():
    assert normalize_time_to_12h("14:30 PM") == "02:30 PM"
    assert normalize_time_to_12h("15:00 PM") == "03:00 PM"


def test_rejects_non_12_hour_output():
    assert validate_12h_time_format("02:30 PM") is True
    assert validate_12h_time_format("14:30 PM") is False


def test_dual_source_verification_requires_exact_date_and_start_time():
    ocr = {"interview_date": "2026-07-25", "start_time": "10:30"}
    vision = {"interview_date": "2026-07-25", "start_time": "10:30 AM"}
    wrong_time = {"interview_date": "2026-07-25", "start_time": "01:00 AM"}

    assert _date_time_agree(ocr, vision) is True
    assert _date_time_agree(ocr, wrong_time) is False


def test_vision_prompt_prioritizes_explicit_invite_date_over_relative_ui_label():
    assert "explicit interview date" in INVITE_EXTRACTION_PROMPT
    assert "Ignore those relative labels" in INVITE_EXTRACTION_PROMPT
    assert "leave interview_date empty" in INVITE_EXTRACTION_PROMPT


def test_ollama_only_mode_is_explicit_and_reversible(monkeypatch):
    monkeypatch.delenv("INVITE_EXTRACTION_MODE", raising=False)
    assert _ollama_only_test_mode() is False

    monkeypatch.setenv("INVITE_EXTRACTION_MODE", "ollama_only")
    assert _ollama_only_test_mode() is True


def test_ollama_only_mode_never_calls_ocr(monkeypatch):
    monkeypatch.setenv("INVITE_EXTRACTION_MODE", "ollama_only")
    monkeypatch.setattr(invite_extract, "_is_ollama_available", lambda: True)

    def fail_if_called(_image):
        raise AssertionError("OCR must not run in Ollama-only mode")

    monkeypatch.setattr(invite_extract, "_run_tesseract_ocr", fail_if_called)
    monkeypatch.setattr(
        invite_extract,
        "call_ollama_vision_model",
        lambda *_args, **_kwargs: json.dumps(
            {
                "interview_date": "2026-07-27",
                "start_time": "10:30 AM",
                "end_time": "11:15 AM",
                "interview_round": "L1",
                "confidence_score": 91,
                "missing_fields": [],
                "warnings": [],
                "looks_like_interview_invite": True,
                "is_payment_screenshot": False,
            }
        ),
    )

    result = invite_extract.extract_interview_invite_with_ollama(b"image", "image/jpeg")

    assert result["ollama_only_test"] is True
    assert result["extraction_method"] == "ollama_only_test"
    assert result["interview_date"] == "2026-07-27"
    assert result["auto_booking_safe"] is False
    assert result["manual_fields_required"] is True
    assert result["backup_model"] == ""


def test_ollama_only_mode_does_not_fall_back_to_another_vision_model(monkeypatch):
    monkeypatch.setenv("INVITE_EXTRACTION_MODE", "ollama_only")
    monkeypatch.setattr(invite_extract, "_is_ollama_available", lambda: True)
    calls = []

    def no_response(model, *_args, **_kwargs):
        calls.append(model)
        return None

    monkeypatch.setattr(invite_extract, "call_ollama_vision_model", no_response)
    result = invite_extract.extract_interview_invite_with_ollama(b"image", "image/jpeg")

    assert calls == [invite_extract.OLLAMA_VISION_MODEL]
    assert result["ollama_only_test"] is True
    assert result["auto_booking_safe"] is False
