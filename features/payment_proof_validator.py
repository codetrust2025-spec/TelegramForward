"""Validate payment proof screenshots using free OCR (Tesseract).

Checks if an uploaded image contains payment-related text indicators.
Rejects images that are clearly not payment receipts (interview invites, random photos, etc.)
"""
from __future__ import annotations

import io
import re
from typing import Optional


# Keywords that indicate a payment screenshot
PAYMENT_KEYWORDS = {
    # Transaction types
    "upi", "neft", "imps", "rtgs", "transfer", "transaction",
    "payment", "paid", "credited", "debited", "received",
    "successful", "success", "completed",
    # Apps / banks
    "phonepe", "gpay", "google pay", "paytm", "bhim", "cred",
    "hdfc", "icici", "sbi", "axis", "kotak", "idfc", "yes bank",
    "canara", "pnb", "bob", "union bank", "indian bank",
    # Reference numbers
    "utr", "ref no", "reference", "txn id", "transaction id",
    "order id", "rrn",
    # Currency
    "inr", "rupee",
}

# Patterns that strongly indicate payment
PAYMENT_PATTERNS = [
    r"₹\s*[\d,]+",           # ₹5,000 or ₹ 10000
    r"rs\.?\s*[\d,]+",       # Rs.5000 or Rs 10,000
    r"utr[:\s]*\w+",         # UTR: ABC123
    r"transaction\s*id",     # Transaction ID
    r"ref\s*(no|number|id)", # Ref No / Reference Number
    r"\d{12,}",              # Long transaction numbers (12+ digits)
]

# Minimum keyword matches to consider valid
MIN_KEYWORD_MATCHES = 2


def validate_payment_proof(image_data: bytes, mime_type: str = "", expected_amount: int = 0) -> tuple[bool, str]:
    """Validate if the image looks like a payment screenshot.
    
    Returns (is_valid, reason).
    - (True, "") if it looks like a payment proof
    - (False, "reason") if it doesn't look like one
    
    If expected_amount > 0, also checks that the detected amount is reasonable.
    """
    if not image_data:
        return False, "Empty image"
    
    text = _extract_text(image_data, mime_type)
    if text is None:
        # OCR not available — allow the upload (don't block if OCR fails)
        print("[PAYMENT-PROOF-VALIDATOR] OCR returned None (unavailable)")
        return True, ""
    
    if not text.strip():
        # Could not extract any text — might be a photo of cash/handwritten receipt
        print("[PAYMENT-PROOF-VALIDATOR] OCR returned empty text")
        return True, ""
    
    text_lower = text.lower()
    print(f"[PAYMENT-PROOF-VALIDATOR] OCR text (first 500 chars): {text[:500]!r}")
    
    # Check for payment keywords
    keyword_matches = sum(1 for kw in PAYMENT_KEYWORDS if kw in text_lower)
    
    # Check for payment patterns (₹ amounts, UTR numbers, etc.)
    pattern_matches = sum(1 for pat in PAYMENT_PATTERNS if re.search(pat, text_lower))
    
    print(f"[PAYMENT-PROOF-VALIDATOR] keywords={keyword_matches}, patterns={pattern_matches}")
    
    # If we find enough indicators, it's valid as a payment screenshot
    if keyword_matches >= MIN_KEYWORD_MATCHES or pattern_matches >= 1:
        # Now check the amount if expected_amount is provided
        if expected_amount > 0:
            detected_amount = _extract_max_amount(text)
            print(f"[PAYMENT-PROOF-VALIDATOR] detected_amount={detected_amount}, expected={expected_amount}")
            if detected_amount > 0:
                # Amount must match expected (within 5% tolerance for OCR errors)
                # OR be greater than expected (overpayment is OK)
                tolerance = expected_amount * 0.05
                if detected_amount < (expected_amount - tolerance):
                    return False, (
                        f"Payment amount detected: ₹{detected_amount:,.0f}. "
                        f"But ₹{expected_amount:,} is due. "
                        f"Upload a screenshot showing the full ₹{expected_amount:,} payment."
                    )
                # Also reject if detected amount doesn't make sense
                # (e.g., OCR misread ₹7k as ₹27k — reject amounts that aren't
                # a clean multiple of the expected or a recognizable payment)
                if detected_amount != expected_amount and detected_amount > expected_amount:
                    # Check if this could be an OCR misread by checking if
                    # removing leading digit(s) gives expected or a partial
                    amt_str = str(int(detected_amount))
                    for i in range(1, len(amt_str)):
                        partial = int(amt_str[i:])
                        if partial > 0 and partial < expected_amount:
                            return False, (
                                f"Payment amount detected: ₹{detected_amount:,.0f} (may be misread). "
                                f"₹{expected_amount:,} is due. "
                                f"Upload a screenshot showing the full ₹{expected_amount:,} payment."
                            )
            else:
                # Could not detect any amount — require full amount proof
                return False, (
                    f"Could not detect payment amount in screenshot. "
                    f"₹{expected_amount:,} is due. "
                    f"Upload a clear screenshot showing the full ₹{expected_amount:,} payment amount."
                )
        return True, ""
    
    # Check if it looks like an interview invite (common false upload)
    interview_keywords = {"interview", "meeting", "teams", "zoom", "calendar", "invite", "scheduled"}
    interview_matches = sum(1 for kw in interview_keywords if kw in text_lower)
    if interview_matches >= 2:
        return False, "This looks like an interview invite, not a payment receipt. Upload a UPI/bank transfer screenshot instead."
    
    # Generic rejection — not enough payment indicators
    if keyword_matches == 0 and pattern_matches == 0:
        return False, "This doesn't look like a payment screenshot. Upload a UPI, PhonePe, GPay, or bank transfer receipt."
    
    # Borderline — allow with 1 keyword match
    return True, ""


def _extract_max_amount(text: str) -> float:
    """Extract the payment amount from the text.
    
    Strategy: find the most frequently occurring amount (appears 2+ times),
    which is more reliable than max (OCR often misreads ₹ symbol as a digit).
    Falls back to the max ₹-prefixed amount if no repeats found.
    """
    all_amounts = []
    
    # Match ₹X,XXX or Rs.X,XXX patterns
    for match in re.finditer(r'₹\s*([\d,]+(?:\.\d{1,2})?)', text):
        try:
            all_amounts.append(float(match.group(1).replace(',', '')))
        except ValueError:
            pass
    for match in re.finditer(r'[Rr][Ss]\.?\s*([\d,]+(?:\.\d{1,2})?)', text):
        try:
            all_amounts.append(float(match.group(1).replace(',', '')))
        except ValueError:
            pass
    
    # Also match comma-formatted numbers (Indian format: 1,00,000 or 10,000)
    for match in re.finditer(r'(\d{1,3}(?:,\d{2,3})*(?:\.\d{1,2})?)', text):
        try:
            val = float(match.group(1).replace(',', ''))
            if 100 <= val <= 1000000:
                all_amounts.append(val)
        except ValueError:
            pass
    
    if not all_amounts:
        return 0
    
    # Count frequency of each amount
    from collections import Counter
    counts = Counter(all_amounts)
    
    # If any amount appears 2+ times, it's likely the real transaction amount
    repeated = [(amt, cnt) for amt, cnt in counts.items() if cnt >= 2]
    if repeated:
        # Return the repeated amount (most frequent, then highest if tie)
        repeated.sort(key=lambda x: (-x[1], -x[0]))
        return repeated[0][0]
    
    # No repeats — return the smallest ₹-prefixed amount between ₹100 and ₹10L
    # (smaller is safer — OCR tends to ADD digits, not remove them)
    valid = [a for a in all_amounts if 100 <= a <= 1000000]
    if valid:
        return min(valid)
    
    return max(all_amounts) if all_amounts else 0


def _extract_text(image_data: bytes, mime_type: str = "") -> Optional[str]:
    """Extract text from image using Tesseract OCR. Returns None if OCR unavailable."""
    try:
        from PIL import Image
        import pytesseract
        
        img = Image.open(io.BytesIO(image_data))
        # Convert to RGB if needed
        if img.mode in ("RGBA", "P"):
            img = img.convert("RGB")
        
        # Extract text
        text = pytesseract.image_to_string(img, lang="eng")
        return text
    except ImportError:
        # PIL or pytesseract not installed — skip validation
        return None
    except Exception:
        # Any OCR error — skip validation (don't block uploads)
        return None


# ── Interview Invite Validator ──────────────────────────────────────────────────

INVITE_KEYWORDS = {
    "interview", "meeting", "teams", "zoom", "google meet", "calendar",
    "invite", "scheduled", "join", "link", "webex", "hangouts",
    "video call", "conference", "agenda", "organizer", "accepted",
    "pm", "am", "ist", "time", "date",
}

INVITE_PATTERNS = [
    r"https?://teams\.microsoft\.com",
    r"https?://zoom\.us",
    r"https?://meet\.google\.com",
    r"https?://.*\.webex\.com",
    r"\d{1,2}:\d{2}\s*(am|pm|AM|PM)",
    r"(Mon|Tue|Wed|Thu|Fri|Sat|Sun)",
    r"(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)",
]


def validate_interview_invite(image_data: bytes, mime_type: str = "") -> tuple[bool, str]:
    """Validate if the image looks like an interview invite screenshot.
    
    Returns (is_valid, reason).
    """
    if not image_data:
        return False, "Empty image"
    
    text = _extract_text(image_data, mime_type)
    if text is None:
        return True, ""  # OCR unavailable — allow
    
    if not text.strip():
        return True, ""  # No text — could be calendar screenshot, allow
    
    text_lower = text.lower()
    
    keyword_matches = sum(1 for kw in INVITE_KEYWORDS if kw in text_lower)
    pattern_matches = sum(1 for pat in INVITE_PATTERNS if re.search(pat, text))
    
    if keyword_matches >= 2 or pattern_matches >= 1:
        return True, ""
    
    # Check if it looks like a payment screenshot (wrong upload)
    payment_matches = sum(1 for kw in PAYMENT_KEYWORDS if kw in text_lower)
    if payment_matches >= 2:
        return False, "This looks like a payment screenshot, not an interview invite. Upload your Teams/Zoom/Calendar interview invite instead."
    
    # Generic — not enough interview indicators
    if keyword_matches == 0 and pattern_matches == 0:
        return False, "This doesn't look like an interview invite. Upload a screenshot from Teams, Zoom, Google Calendar, or your email showing the interview details."
    
    return True, ""


def validate_handler_payout_proof(image_data: bytes, mime_type: str = "") -> tuple[bool, str]:
    """Validate if the image looks like a payment/transfer proof for handler payout."""
    if not image_data:
        return False, "Empty image"
    
    text = _extract_text(image_data, mime_type)
    if text is None:
        return True, ""  # OCR unavailable — allow
    
    if not text.strip():
        return True, ""
    
    text_lower = text.lower()
    
    keyword_matches = sum(1 for kw in PAYMENT_KEYWORDS if kw in text_lower)
    pattern_matches = sum(1 for pat in PAYMENT_PATTERNS if re.search(pat, text_lower))
    
    if keyword_matches >= 2 or pattern_matches >= 1:
        return True, ""
    
    if keyword_matches == 0 and pattern_matches == 0:
        return False, "This doesn't look like a payment screenshot. Upload a UPI/bank transfer receipt showing the payout."
    
    return True, ""
