from features.company_payment_verification import (
    configured_company_account_numbers,
    configured_company_phone_numbers,
    configured_company_upi_ids,
    verify_company_payment,
)
from features.ollama_payment_extract import _extract_amount_from_text, _ocr_regex_extraction


def _receipt(**patch):
    receipt = {
        "is_payment_screenshot": True,
        "amount": 5000,
        "receiver_name": "J Ravinder",
        "receiver_upi_id": "company@upi",
        "utr_number": "482681255068",
        "status": "success",
    }
    receipt.update(patch)
    return receipt


def test_company_payment_accepts_configured_company_upi():
    verdict = verify_company_payment(
        _receipt(), 5000,
        accepted_upi_ids={"company@upi"},
        accepted_phone_numbers={"8639074573"},
    )

    assert verdict["verified"] is True
    assert verdict["reasons"] == []


def test_official_company_payment_defaults_survive_config_loader_failure(monkeypatch):
    monkeypatch.delenv("COMPANY_PAYMENT_UPI_IDS", raising=False)
    monkeypatch.delenv("COMPANY_PAYMENT_PHONE_NUMBERS", raising=False)

    assert configured_company_upi_ids() == {"company@upi"}
    assert configured_company_phone_numbers() == {"8639074573"}


def test_registered_referrer_payment_is_accepted():
    verdict = verify_company_payment(
        _receipt(
            receiver_name="Referrer One",
            receiver_upi_id="referrer@upi",
        ),
        5000,
        accepted_upi_ids={"company@upi"},
        accepted_phone_numbers={"8639074573"},
    )

    assert verdict["verified"] is True
    assert verdict["receiver_type"] == "referrer"
    assert verdict["reasons"] == []


def test_receipt_without_visible_payee_fails_closed():
    verdict = verify_company_payment(
        _receipt(receiver_upi_id=""),
        5000,
        accepted_upi_ids={"company@upi"},
        accepted_phone_numbers={"8639074573"},
    )

    assert verdict["verified"] is False
    assert "receiving UPI ID or phone number is not visible" in " ".join(verdict["reasons"])


def test_failed_or_partial_company_payment_is_rejected():
    verdict = verify_company_payment(
        _receipt(amount=3000, status="failed"),
        5000,
        accepted_upi_ids={"company@upi"},
        accepted_phone_numbers={"8639074573"},
    )

    assert verdict["verified"] is False
    reasons = " ".join(verdict["reasons"])
    assert "successful, completed" in reasons
    assert "full ₹5,000" in reasons


def test_compact_company_upi_success_without_utr_is_allowed():
    verdict = verify_company_payment(
        _receipt(utr_number=""),
        5000,
        accepted_upi_ids={"company@upi"},
        accepted_phone_numbers={"8639074573"},
    )

    assert verdict["verified"] is True


def test_company_payment_phone_is_allowed_without_upi():
    verdict = verify_company_payment(
        _receipt(
            amount=16000,
            receiver_name="Company Receiver",
            receiver_upi_id="",
            receiver_phone="+919000000001",
        ),
        16000,
        accepted_upi_ids={"company@upi"},
        accepted_phone_numbers={"8639074573"},
    )

    assert verdict["verified"] is True
    assert verdict["receiver_phone"] == "8639074573"


def test_stored_company_payment_accepts_configured_bank_account(monkeypatch):
    from features.company_payment_verification import stored_proof_is_verified_company_payment

    monkeypatch.setenv("COMPANY_PAYMENT_ACCOUNT_NUMBERS", "1234567896367")
    assert configured_company_account_numbers() == {"1234567896367"}
    assert stored_proof_is_verified_company_payment({
        "company_payment_verified": True,
        "receiver_account": "XXXXXX6367",
    })


def test_ocr_fast_path_extracts_company_upi_from_compact_receipt():
    result = _ocr_regex_extraction(
        "Transaction Successful\n₹15,000.00\nPaid to J RAVINDER\n"
        "PhonePe • company@upi\n30 June 2026, 8:01pm"
    )

    assert result is not None
    assert result["receiver_upi_id"] == "company@upi"


def test_ocr_fast_path_extracts_company_payment_phone():
    result = _ocr_regex_extraction(
        "Transaction Successful\nPaid to Company Receiver\n+919000000001\n"
        "₹16,000\nUTR: 633424783763"
    )

    assert result is not None
    assert result["receiver_phone"] == "+919000000001"


def test_ocr_amount_survives_when_rupee_symbol_is_dropped():
    text = "Paid to ravindra job hunter\nUTR: 265087185302\n15,000\n15,000"

    assert _extract_amount_from_text(text) == 15000
    result = _ocr_regex_extraction(text)
    assert result is not None
    assert result["amount"] == 15000
