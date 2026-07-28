import core.ocr_policy as policy
import features.ollama_payment_extract as payment_extract


def test_ocr_is_enabled_by_default(monkeypatch):
    monkeypatch.delenv("OCR_ENABLED", raising=False)
    assert policy.ocr_enabled() is True


def test_global_ocr_kill_switch_accepts_common_false_values(monkeypatch):
    for value in ("false", "0", "off", "disabled", "no"):
        monkeypatch.setenv("OCR_ENABLED", value)
        assert policy.ocr_enabled() is False


def test_payment_extraction_bypasses_ocr_when_globally_disabled(monkeypatch):
    monkeypatch.setenv("OCR_ENABLED", "false")
    monkeypatch.setattr(payment_extract, "_is_ollama_available", lambda: True)

    def fail_if_called(_image):
        raise AssertionError("OCR must not run while globally disabled")

    monkeypatch.setattr(payment_extract, "_run_tesseract_ocr", fail_if_called)
    monkeypatch.setattr(
        payment_extract,
        "_call_vision_model",
        lambda *_args, **_kwargs: (
            '{"amount":5000,"receiver_name":"J Ravinder",'
            '"receiver_upi_id":"company@upi","utr_number":"459877656303",'
            '"status":"success","confidence_score":98,"is_payment_screenshot":true}'
        ),
    )

    result = payment_extract.extract_payment_with_ollama(b"image", "image/jpeg")

    assert result["extraction_method"] == "vision"
    assert result["receiver_upi_id"] == "company@upi"
