"""Ollama vision model integration for payment proof screenshot extraction.

Reads UPI/bank transfer screenshots and extracts structured payment data:
amount, sender, receiver, date, UTR/reference number, payment app, status.

Auto-verifies against the candidate's due amount (₹10k+ threshold for slot confirmation).

Architecture (same as ollama_invite_extract.py):
  - Ollama runs on developer laptop (64GB RAM)
  - Tunneled to VPS via SSH reverse tunnel (localhost:11434)
  - Hybrid flow: OCR fast path → text model → vision model fallback

Primary model: qwen2.5vl:7b (reliable structured extraction)
Backup model: moondream (lightweight fallback)
Falls back to existing OCR regex if both AI models fail.
"""
from __future__ import annotations

import base64
import json
import os
import re
import time
import logging
from datetime import date, datetime
from typing import Any

import httpx

logger = logging.getLogger(__name__)

# ── Configuration (shared with ollama_invite_extract) ───────────────────────
OLLAMA_BASE_URL = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_VISION_MODEL = os.environ.get("OLLAMA_VISION_MODEL", "qwen2.5vl:7b")
OLLAMA_BACKUP_VISION_MODEL = os.environ.get("OLLAMA_BACKUP_VISION_MODEL", "moondream")
OLLAMA_REASONING_MODEL = os.environ.get("OLLAMA_REASONING_MODEL", "qwen2.5:7b")
OLLAMA_TIMEOUT = int(os.environ.get("OLLAMA_TIMEOUT", "900"))
OLLAMA_TEXT_TIMEOUT = int(os.environ.get("OLLAMA_TEXT_TIMEOUT", "60"))


# ── Prompt ──────────────────────────────────────────────────────────────────
PAYMENT_EXTRACTION_PROMPT = """You are a payment screenshot extraction assistant for Indian UPI/bank transfers.
Read the uploaded screenshot carefully. It may be from PhonePe, GPay, Paytm, CRED, BHIM, or any bank app.

Return ONLY valid JSON. Do not explain. Do not use markdown. Do not wrap JSON inside code blocks.

IMPORTANT: Today's date is {today}.

Extract these fields from the payment screenshot:

Schema:
{{"amount": 0, "sender_name": "", "sender_upi_id": "", "receiver_name": "", "receiver_upi_id": "", "utr_number": "", "reference_number": "", "transaction_id": "", "payment_app": "", "bank_name": "", "payment_date": "YYYY-MM-DD", "payment_time": "hh:mm AM/PM", "status": "", "payment_method": "", "confidence_score": 0, "is_payment_screenshot": true, "warnings": [], "raw_detected_text": ""}}

Rules:
- "amount" must be a number (no ₹ symbol, no commas). Example: 10000 not "₹10,000"
- "status" should be one of: "success", "pending", "failed", "unknown"
- "payment_method" should be one of: "upi", "neft", "imps", "rtgs", "cash", "unknown"
- "payment_app" examples: "PhonePe", "GPay", "Paytm", "CRED", "BHIM", "HDFC", "SBI"
- "utr_number" is the unique transaction reference (12-digit alphanumeric for UPI)
- "confidence_score" is 0-100 based on how clearly you can read the payment details
- If the image is NOT a payment screenshot, set "is_payment_screenshot": false and "amount": 0
- If a field is not visible in the screenshot, leave it as empty string or 0
"""


# ── Empty result template ───────────────────────────────────────────────────
def _empty_extraction() -> dict[str, Any]:
    return {
        "amount": 0,
        "sender_name": "",
        "sender_upi_id": "",
        "receiver_name": "",
        "receiver_upi_id": "",
        "utr_number": "",
        "reference_number": "",
        "transaction_id": "",
        "payment_app": "",
        "bank_name": "",
        "payment_date": "",
        "payment_time": "",
        "status": "unknown",
        "payment_method": "unknown",
        "confidence_score": 0,
        "is_payment_screenshot": False,
        "warnings": [],
        "raw_detected_text": "",
        "extraction_source": "",
        "extraction_method": "",
        "primary_model": "",
        "backup_model": "",
        "detected_by": "",
        # Verification fields (populated by verify_payment_against_due)
        "verified": False,
        "verification_result": "",
        "amount_due": 0,
        "amount_sufficient": False,
    }


# ── Ollama helpers (reuse pattern from ollama_invite_extract) ───────────────
def _is_ollama_available() -> bool:
    """Check if Ollama is running and accessible."""
    try:
        resp = httpx.get(f"{OLLAMA_BASE_URL}/api/tags", timeout=5)
        return resp.status_code == 200
    except Exception:
        return False


def _call_vision_model(
    model_name: str,
    image_base64: str,
    prompt: str,
    *,
    timeout: int = OLLAMA_TIMEOUT,
) -> str | None:
    """Call Ollama vision model with an image and prompt."""
    try:
        payload = {
            "model": model_name,
            "messages": [
                {
                    "role": "user",
                    "content": prompt,
                    "images": [image_base64],
                }
            ],
            "stream": False,
            "options": {
                "temperature": 0.1,
                "num_predict": 2048,
            },
        }
        resp = httpx.post(
            f"{OLLAMA_BASE_URL}/api/chat",
            json=payload,
            timeout=timeout,
        )
        if resp.status_code == 200:
            data = resp.json()
            content = data.get("message", {}).get("content", "")
            return content.strip() if content else None
        logger.warning("Vision model %s returned status %d", model_name, resp.status_code)
        return None
    except httpx.TimeoutException:
        logger.warning("Vision model %s timed out after %ds", model_name, timeout)
        return None
    except Exception as exc:
        logger.warning("Vision model %s error: %s", model_name, exc)
        return None


def _call_text_model(prompt: str, *, timeout: int = OLLAMA_TEXT_TIMEOUT) -> str | None:
    """Call Ollama text model (qwen2.5:7b) for fast OCR text cleanup."""
    try:
        payload = {
            "model": OLLAMA_REASONING_MODEL,
            "messages": [
                {"role": "user", "content": prompt}
            ],
            "stream": False,
            "options": {
                "temperature": 0.1,
                "num_predict": 2048,
            },
        }
        resp = httpx.post(
            f"{OLLAMA_BASE_URL}/api/chat",
            json=payload,
            timeout=timeout,
        )
        if resp.status_code == 200:
            data = resp.json()
            content = data.get("message", {}).get("content", "")
            return content.strip() if content else None
        return None
    except Exception as exc:
        logger.warning("Text model error: %s", exc)
        return None


# ── JSON parsing ────────────────────────────────────────────────────────────
def _parse_json_response(raw: str) -> dict[str, Any] | None:
    """Parse JSON from model response, handling markdown code blocks."""
    if not raw:
        return None
    text = raw.strip()
    # Strip markdown code blocks
    if text.startswith("```"):
        lines = text.split("\n")
        lines = [l for l in lines if not l.strip().startswith("```")]
        text = "\n".join(lines).strip()
    # Try direct parse
    try:
        result = json.loads(text)
        if isinstance(result, dict):
            return result
    except json.JSONDecodeError:
        pass
    # Try to find JSON object in the text
    match = re.search(r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}', text, re.DOTALL)
    if match:
        try:
            result = json.loads(match.group())
            if isinstance(result, dict):
                return result
        except json.JSONDecodeError:
            pass
    return None


# ── OCR fallback (Tesseract) ───────────────────────────────────────────────
def _run_tesseract_ocr(image_data: bytes) -> str | None:
    """Extract text from image using Tesseract."""
    try:
        import io
        from PIL import Image
        import pytesseract

        img = Image.open(io.BytesIO(image_data))
        if img.mode in ("RGBA", "P"):
            img = img.convert("RGB")
        return pytesseract.image_to_string(img, lang="eng")
    except Exception as exc:
        logger.warning("Tesseract OCR failed: %s", exc)
        return None


def _extract_amount_from_text(text: str) -> float:
    """Extract payment amount from OCR text using regex patterns."""
    amounts = []
    # ₹X,XXX patterns
    for m in re.finditer(r'₹\s*([\d,]+(?:\.\d{1,2})?)', text):
        try:
            amounts.append(float(m.group(1).replace(',', '')))
        except ValueError:
            pass
    # Rs.X,XXX patterns
    for m in re.finditer(r'[Rr][Ss]\.?\s*([\d,]+(?:\.\d{1,2})?)', text):
        try:
            amounts.append(float(m.group(1).replace(',', '')))
        except ValueError:
            pass
    # %X,XXX (OCR misread of ₹)
    for m in re.finditer(r'%\s*([\d,]+(?:\.\d{1,2})?)', text):
        try:
            val = float(m.group(1).replace(',', ''))
            if val >= 500:
                amounts.append(val)
        except ValueError:
            pass
    if not amounts:
        return 0
    # Return the most common amount, or the largest reasonable one
    from collections import Counter
    counts = Counter(int(a) for a in amounts if 500 <= a <= 1_000_000)
    if counts:
        most_common = counts.most_common(1)[0]
        if most_common[1] >= 2:
            return float(most_common[0])
        return float(max(counts.keys()))
    return 0


def _extract_utr_from_text(text: str) -> str:
    """Extract UTR/reference number from OCR text."""
    # UTR pattern (12-digit number)
    m = re.search(r'(?:UTR|utr|Utr)[:\s]*([A-Za-z0-9]{12,22})', text)
    if m:
        return m.group(1)
    # Reference number pattern
    m = re.search(r'(?:Ref|ref|REF)\s*(?:No|no|NO)?[:\s]*([A-Za-z0-9]{8,22})', text)
    if m:
        return m.group(1)
    # Transaction ID
    m = re.search(r'(?:Txn|txn|TXN|Transaction)\s*(?:ID|Id|id)?[:\s]*([A-Za-z0-9]{8,22})', text)
    if m:
        return m.group(1)
    # Standalone 12-digit number (likely UTR)
    m = re.search(r'\b(\d{12})\b', text)
    if m:
        return m.group(1)
    return ""


def _detect_payment_app(text: str) -> str:
    """Detect payment app from OCR text."""
    text_lower = text.lower()
    apps = [
        ("phonepe", "PhonePe"),
        ("phone pe", "PhonePe"),
        ("gpay", "GPay"),
        ("google pay", "GPay"),
        ("paytm", "Paytm"),
        ("cred", "CRED"),
        ("bhim", "BHIM"),
        ("hdfc", "HDFC"),
        ("icici", "ICICI"),
        ("sbi", "SBI"),
        ("axis", "Axis"),
        ("kotak", "Kotak"),
        ("idfc", "IDFC"),
        ("yes bank", "Yes Bank"),
    ]
    for keyword, name in apps:
        if keyword in text_lower:
            return name
    return ""


def _detect_status(text: str) -> str:
    """Detect payment status from OCR text."""
    text_lower = text.lower()
    if any(w in text_lower for w in ("success", "successful", "completed", "paid", "done")):
        return "success"
    if any(w in text_lower for w in ("pending", "processing", "initiated")):
        return "pending"
    if any(w in text_lower for w in ("failed", "failure", "declined", "rejected")):
        return "failed"
    return "unknown"


def _extract_date_from_text(text: str) -> str:
    """Try to extract payment date from OCR text."""
    # DD Mon YYYY or DD-Mon-YYYY
    m = re.search(
        r'(\d{1,2})\s*[-/]?\s*(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\w*\s*[-/]?\s*(\d{2,4})',
        text, re.IGNORECASE
    )
    if m:
        day = int(m.group(1))
        mon_str = m.group(2)[:3].capitalize()
        year = int(m.group(3))
        if year < 100:
            year += 2000
        months = {"Jan": 1, "Feb": 2, "Mar": 3, "Apr": 4, "May": 5, "Jun": 6,
                  "Jul": 7, "Aug": 8, "Sep": 9, "Oct": 10, "Nov": 11, "Dec": 12}
        mon = months.get(mon_str, 0)
        if mon and 1 <= day <= 31:
            return f"{year}-{mon:02d}-{day:02d}"
    # DD/MM/YYYY or DD-MM-YYYY
    m = re.search(r'(\d{1,2})[/\-](\d{1,2})[/\-](\d{2,4})', text)
    if m:
        day, mon, year = int(m.group(1)), int(m.group(2)), int(m.group(3))
        if year < 100:
            year += 2000
        if 1 <= mon <= 12 and 1 <= day <= 31:
            return f"{year}-{mon:02d}-{day:02d}"
    return ""


# ── OCR-based fast extraction (no AI needed) ───────────────────────────────
def _ocr_regex_extraction(ocr_text: str) -> dict[str, Any] | None:
    """Try to extract payment details from OCR text using regex only.
    
    Returns a filled dict if we can get amount + (UTR or status=success).
    """
    amount = _extract_amount_from_text(ocr_text)
    if amount < 500:
        return None  # Not a meaningful payment amount

    utr = _extract_utr_from_text(ocr_text)
    status = _detect_status(ocr_text)
    app = _detect_payment_app(ocr_text)
    pay_date = _extract_date_from_text(ocr_text)

    # Need at least amount + one of (UTR, success status) to trust regex
    if not utr and status != "success":
        return None

    result = _empty_extraction()
    result["amount"] = int(amount)
    result["utr_number"] = utr
    result["status"] = status
    result["payment_app"] = app
    result["payment_date"] = pay_date
    result["is_payment_screenshot"] = True
    result["confidence_score"] = min(85, 40 + (20 if utr else 0) + (15 if status == "success" else 0) + (10 if app else 0))
    result["extraction_source"] = "ocr_regex"
    result["extraction_method"] = "regex_fast"
    result["primary_model"] = "tesseract+regex"
    result["detected_by"] = "OCR + regex"
    return result


# ── Text model cleanup (OCR text → structured JSON) ────────────────────────
def _try_text_model_cleanup(ocr_text: str) -> dict[str, Any] | None:
    """Send OCR text to qwen2.5:7b for structured extraction."""
    today = date.today()
    prompt = f"""You are a payment screenshot text parser.
The following text was extracted via OCR from a UPI/bank payment screenshot.
Extract the payment details into JSON.

Return ONLY valid JSON. No explanation. No markdown.

Today's date: {today.isoformat()}

OCR Text:
---
{ocr_text[:3000]}
---

Schema:
{{"amount": 0, "sender_name": "", "sender_upi_id": "", "receiver_name": "", "receiver_upi_id": "", "utr_number": "", "reference_number": "", "transaction_id": "", "payment_app": "", "bank_name": "", "payment_date": "YYYY-MM-DD", "payment_time": "hh:mm AM/PM", "status": "", "payment_method": "", "confidence_score": 0, "is_payment_screenshot": true, "warnings": []}}

Rules:
- "amount" must be a number (no ₹, no commas). Example: 10000
- "status": "success", "pending", "failed", or "unknown"
- "payment_method": "upi", "neft", "imps", "rtgs", "cash", or "unknown"
- If the text is NOT from a payment screenshot, set "is_payment_screenshot": false
"""
    response = _call_text_model(prompt)
    if not response:
        return None
    parsed = _parse_json_response(response)
    if not parsed:
        return None
    if not parsed.get("is_payment_screenshot"):
        return None
    # Ensure amount is a number
    try:
        parsed["amount"] = int(float(parsed.get("amount", 0)))
    except (ValueError, TypeError):
        parsed["amount"] = 0
    if parsed["amount"] < 500:
        return None
    return parsed


# ── Prompt builder ──────────────────────────────────────────────────────────
def _get_payment_prompt() -> str:
    """Build the payment extraction prompt with today's date."""
    today = date.today()
    return PAYMENT_EXTRACTION_PROMPT.format(today=today.isoformat())


# ── Main extraction function ────────────────────────────────────────────────
def extract_payment_with_ollama(
    image_data: bytes,
    mime_type: str = "image/jpeg",
) -> dict[str, Any]:
    """Extract payment details from a screenshot using hybrid OCR + AI approach.

    Hybrid flow (optimized for speed):
      1. OCR image → raw text (Tesseract, instant)
      2. If OCR finds amount + UTR/status, return immediately (regex fast path)
      3. If OCR has text but regex incomplete, send to qwen2.5:7b text model (~10-30s)
      4. Only if OCR fails, call qwen2.5vl:7b vision model (~5 min)
      5. If vision fails, try moondream backup
      6. If all AI fails, return whatever regex found

    Ollama runs on the developer's laptop, tunneled to VPS via SSH.
    """
    # Check if Ollama is reachable
    ollama_available = _is_ollama_available()
    if not ollama_available:
        logger.info("Ollama not reachable (SSH tunnel may be down), using OCR only")

    # ── Step 1: OCR + regex (instant) ───────────────────────────────────────
    ocr_text = _run_tesseract_ocr(image_data)

    if ocr_text and len(ocr_text) > 10:
        logger.info("OCR extracted %d chars for payment", len(ocr_text))

        # Try regex first (instant)
        regex_result = _ocr_regex_extraction(ocr_text)
        if regex_result and regex_result["amount"] >= 500:
            logger.info(
                "Regex found amount=₹%d, UTR=%s, status=%s — using fast path",
                regex_result["amount"],
                regex_result.get("utr_number", ""),
                regex_result.get("status", ""),
            )
            regex_result["raw_detected_text"] = ocr_text[:1000]
            return regex_result

        # ── Step 2: Text model cleanup (~10-30s) ────────────────────────────
        if ollama_available:
            logger.info("Regex incomplete, trying text model for payment extraction")
            text_result = _try_text_model_cleanup(ocr_text)
            if text_result and text_result.get("amount", 0) >= 500:
                # Merge into our template
                result = _empty_extraction()
                result.update(text_result)
                result["extraction_source"] = "ocr_ai_cleanup"
                result["extraction_method"] = "hybrid_fast"
                result["primary_model"] = OLLAMA_REASONING_MODEL
                result["detected_by"] = f"OCR + {OLLAMA_REASONING_MODEL}"
                result["raw_detected_text"] = ocr_text[:1000]
                result["is_payment_screenshot"] = True
                logger.info(
                    "Text model extracted: amount=₹%d, UTR=%s",
                    result["amount"],
                    result.get("utr_number", ""),
                )
                return result
    else:
        logger.info("OCR text too short (%d chars), going to vision model", len(ocr_text or ""))

    # ── Step 3: Vision model (slow path, ~5 min) ────────────────────────────
    if not ollama_available:
        # Return whatever OCR found (even if incomplete)
        fallback = _empty_extraction()
        if ocr_text:
            fallback["amount"] = int(_extract_amount_from_text(ocr_text))
            fallback["utr_number"] = _extract_utr_from_text(ocr_text)
            fallback["status"] = _detect_status(ocr_text)
            fallback["payment_app"] = _detect_payment_app(ocr_text)
            fallback["payment_date"] = _extract_date_from_text(ocr_text)
            fallback["is_payment_screenshot"] = fallback["amount"] >= 500
            fallback["raw_detected_text"] = ocr_text[:1000]
        fallback["extraction_source"] = "ocr_only"
        fallback["extraction_method"] = "ocr_fallback"
        fallback["detected_by"] = "OCR (Ollama unavailable)"
        fallback["confidence_score"] = 30 if fallback["amount"] > 0 else 0
        fallback["warnings"] = ["Ollama unavailable — OCR-only extraction, may be incomplete"]
        return fallback

    img_b64 = base64.b64encode(image_data).decode("utf-8")
    prompt = _get_payment_prompt()

    logger.info("Calling vision model: %s for payment extraction", OLLAMA_VISION_MODEL)
    start = time.time()
    response = _call_vision_model(OLLAMA_VISION_MODEL, img_b64, prompt, timeout=OLLAMA_TIMEOUT)
    elapsed = time.time() - start
    logger.info("Vision model responded in %.1fs", elapsed)

    extracted = None
    used_model = OLLAMA_VISION_MODEL

    if response:
        extracted = _parse_json_response(response)

    # ── Step 4: Backup model (moondream) ────────────────────────────────────
    if not extracted or not extracted.get("is_payment_screenshot"):
        logger.warning("Primary vision failed for payment, trying backup: %s", OLLAMA_BACKUP_VISION_MODEL)
        backup_response = _call_vision_model(
            OLLAMA_BACKUP_VISION_MODEL, img_b64, prompt, timeout=OLLAMA_TIMEOUT
        )
        if backup_response:
            backup_parsed = _parse_json_response(backup_response)
            if backup_parsed and backup_parsed.get("is_payment_screenshot"):
                extracted = backup_parsed
                used_model = OLLAMA_BACKUP_VISION_MODEL

    # ── Build final result ──────────────────────────────────────────────────
    if extracted and extracted.get("is_payment_screenshot"):
        result = _empty_extraction()
        result.update(extracted)
        # Normalize amount to int
        try:
            result["amount"] = int(float(result.get("amount", 0)))
        except (ValueError, TypeError):
            result["amount"] = 0
        result["extraction_source"] = "vision_model"
        result["extraction_method"] = "vision"
        result["primary_model"] = used_model
        result["detected_by"] = f"Vision ({used_model})"
        result["is_payment_screenshot"] = True
        if ocr_text:
            result["raw_detected_text"] = ocr_text[:1000]
        logger.info("Vision extracted: amount=₹%d, UTR=%s", result["amount"], result.get("utr_number", ""))
        return result

    # ── Step 5: Final fallback — return OCR data if any ─────────────────────
    fallback = _empty_extraction()
    if ocr_text:
        fallback["amount"] = int(_extract_amount_from_text(ocr_text))
        fallback["utr_number"] = _extract_utr_from_text(ocr_text)
        fallback["status"] = _detect_status(ocr_text)
        fallback["payment_app"] = _detect_payment_app(ocr_text)
        fallback["payment_date"] = _extract_date_from_text(ocr_text)
        fallback["is_payment_screenshot"] = fallback["amount"] >= 500
        fallback["raw_detected_text"] = ocr_text[:1000]
    fallback["extraction_source"] = "ocr_fallback"
    fallback["extraction_method"] = "ocr_fallback"
    fallback["detected_by"] = "OCR (AI models failed)"
    fallback["confidence_score"] = 25 if fallback["amount"] > 0 else 0
    fallback["warnings"] = ["All AI models failed — OCR-only extraction"]
    return fallback


# ── Verification against candidate due amount ───────────────────────────────
def verify_payment_against_due(
    extraction: dict[str, Any],
    amount_due: int,
    *,
    tolerance_pct: float = 0.05,
) -> dict[str, Any]:
    """Verify extracted payment amount against what's due.

    Adds verification fields to the extraction dict:
      - verified: bool — True if amount meets threshold
      - verification_result: str — human-readable verdict
      - amount_due: int — what was expected
      - amount_sufficient: bool — True if amount >= due (within tolerance)

    tolerance_pct: allow 5% under for OCR misreads (e.g., ₹9,500 read as ₹9500
    when ₹10,000 is due — that's rejected. But ₹9,800 → accept as close enough).
    """
    result = dict(extraction)
    detected = int(result.get("amount", 0))
    result["amount_due"] = amount_due

    if not result.get("is_payment_screenshot"):
        result["verified"] = False
        result["verification_result"] = "Not a payment screenshot"
        result["amount_sufficient"] = False
        return result

    if detected <= 0:
        result["verified"] = False
        result["verification_result"] = "Could not detect payment amount"
        result["amount_sufficient"] = False
        return result

    if amount_due <= 0:
        # No specific amount required — just verify it's a payment
        result["verified"] = True
        result["verification_result"] = f"₹{detected:,} payment detected (no minimum required)"
        result["amount_sufficient"] = True
        return result

    min_acceptable = amount_due * (1 - tolerance_pct)

    if detected >= min_acceptable:
        result["verified"] = True
        result["amount_sufficient"] = True
        if detected >= amount_due:
            result["verification_result"] = (
                f"✓ ₹{detected:,} payment verified (₹{amount_due:,} was due)"
            )
        else:
            result["verification_result"] = (
                f"✓ ₹{detected:,} payment accepted (₹{amount_due:,} due, within tolerance)"
            )
    else:
        result["verified"] = False
        result["amount_sufficient"] = False
        result["verification_result"] = (
            f"✗ ₹{detected:,} detected but ₹{amount_due:,} is due. "
            f"Short by ₹{amount_due - detected:,}."
        )

    return result


# ── Confidence narrative (human-readable summary for payout modal) ──────────

def _rule_based_narrative(
    extraction: dict[str, Any],
    candidate_name: str,
    expected_amount: int,
    received_amount: int,
) -> str:
    """Deterministic narrative when Ollama is unavailable.

    Produces a sentence like:
      "Amount ₹10,000 matches expected ₹10,000 · UTR 123456789012 · PhonePe ·
       date 2025-06-01 · status success — looks valid."
    """
    parts: list[str] = []
    detected = int(extraction.get("amount") or 0)
    due = max(0, expected_amount - received_amount)

    # Amount check
    if detected > 0:
        if due > 0:
            tolerance = due * 0.05
            if detected >= due - tolerance:
                parts.append(f"Amount ₹{detected:,} matches due ₹{due:,}")
            else:
                parts.append(f"Amount ₹{detected:,} detected but ₹{due:,} was due")
        else:
            parts.append(f"Amount ₹{detected:,} detected (candidate is fully paid)")
    else:
        parts.append("Amount not detected")

    # Receiver name check
    receiver = (extraction.get("receiver_name") or "").strip()
    if receiver and candidate_name:
        canon = " ".join(candidate_name.strip().lower().split())
        recv_key = " ".join(receiver.lower().split())
        # Check for partial name overlap
        name_words = [w for w in canon.split() if len(w) > 2]
        if any(w in recv_key for w in name_words):
            parts.append(f"receiver name '{receiver}' matches candidate")
        else:
            parts.append(f"receiver '{receiver}' (verify against candidate name '{candidate_name}')")

    # UTR
    utr = (extraction.get("utr_number") or extraction.get("reference_number") or "").strip()
    if utr:
        parts.append(f"UTR {utr}")

    # App
    app = (extraction.get("payment_app") or "").strip()
    if app:
        parts.append(app)

    # Date
    pay_date = (extraction.get("payment_date") or "").strip()
    if pay_date:
        today_str = date.today().isoformat()
        if pay_date <= today_str:
            parts.append(f"date {pay_date}")
        else:
            parts.append(f"date {pay_date} (future date — verify)")

    # Status
    status = (extraction.get("status") or "unknown").lower()
    if status == "success":
        parts.append("status success")
    elif status == "pending":
        parts.append("status pending — payment not yet settled")
    elif status == "failed":
        parts.append("status failed — do not accept")

    if not parts:
        return "Could not extract payment details — review screenshot manually."

    summary = " · ".join(parts)
    verified = extraction.get("verified", False)
    suffix = " — looks valid." if verified else " — review manually."
    return summary + suffix


_NARRATIVE_PROMPT_TEMPLATE = """You are a concise payment verification assistant for a recruiting operations tool.

A payment screenshot was uploaded for candidate: {candidate_name}
Expected payment: ₹{expected_amount}
Already received: ₹{received_amount}
Amount still due: ₹{due_amount}

Extracted payment details from screenshot:
- Detected amount: ₹{detected_amount}
- Receiver name: {receiver_name}
- UTR / Reference: {utr}
- Payment app: {payment_app}
- Payment date: {payment_date}
- Status: {status}
- Confidence score: {confidence}/100

Write ONE plain-English sentence (max 35 words) summarising whether this payment screenshot looks valid. Mention:
1. Whether the amount matches what's due
2. Whether the receiver name matches the candidate (if available)
3. Whether the date is plausible
4. A brief verdict: "looks valid", "needs review", or "reject"

Do not use bullet points. Do not use markdown. Return only the sentence.
"""


def generate_payment_narrative(
    extraction: dict[str, Any],
    *,
    candidate_name: str = "",
    expected_amount: int = 0,
    received_amount: int = 0,
) -> str:
    """Generate a plain-English confidence summary for the payout modal.

    Uses qwen2.5:7b (fast text model) if Ollama is available, otherwise
    falls back to a deterministic rule-based sentence.

    Example outputs:
      "Amount ₹10,000 matches due · UTR 320022345678 · PhonePe · date 2025-06-01 — looks valid."
      "Amount ₹5,000 detected but ₹10,000 was due — short by ₹5,000, needs review."
    """
    due = max(0, expected_amount - received_amount)
    detected = int(extraction.get("amount") or 0)
    utr = (extraction.get("utr_number") or extraction.get("reference_number") or "").strip() or "—"
    receiver = (extraction.get("receiver_name") or "").strip() or "—"
    app = (extraction.get("payment_app") or "").strip() or "—"
    pay_date = (extraction.get("payment_date") or "").strip() or "—"
    status = (extraction.get("status") or "unknown").strip()
    confidence = int(extraction.get("confidence_score") or 0)

    # Try Ollama text model first (fast, ~10-30s)
    if _is_ollama_available():
        prompt = _NARRATIVE_PROMPT_TEMPLATE.format(
            candidate_name=candidate_name or "Unknown",
            expected_amount=f"{expected_amount:,}" if expected_amount else "0",
            received_amount=f"{received_amount:,}" if received_amount else "0",
            due_amount=f"{due:,}" if due else "0 (fully paid)",
            detected_amount=f"{detected:,}" if detected else "not detected",
            receiver_name=receiver,
            utr=utr,
            payment_app=app,
            payment_date=pay_date,
            status=status,
            confidence=confidence,
        )
        try:
            response = _call_text_model(prompt, timeout=45)
            if response:
                # Strip any stray quotes or markdown the model adds
                narrative = response.strip().strip('"\'`').strip()
                # Sanity: must be a non-empty sentence under 300 chars
                if 10 < len(narrative) < 300:
                    logger.info("Narrative generated by text model (%d chars)", len(narrative))
                    return narrative
        except Exception as exc:
            logger.warning("Narrative generation failed: %s", exc)

    # Fallback: deterministic rule-based narrative
    logger.info("Using rule-based narrative (Ollama unavailable or model failed)")
    return _rule_based_narrative(extraction, candidate_name, expected_amount, received_amount)
