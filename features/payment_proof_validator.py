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
        return True, ""
    
    if not text.strip():
        # Could not extract any text — might be a photo of cash/handwritten receipt
        # Allow it since we can't determine
        return True, ""
    
    text_lower = text.lower()
    
    # Check for payment keywords
    keyword_matches = sum(1 for kw in PAYMENT_KEYWORDS if kw in text_lower)
    
    # Check for payment patterns (₹ amounts, UTR numbers, etc.)
    pattern_matches = sum(1 for pat in PAYMENT_PATTERNS if re.search(pat, text_lower))
    
    # If we find enough indicators, it's valid
    if keyword_matches >= MIN_KEYWORD_MATCHES or pattern_matches >= 1:
        # Now check the amount if expected_amount is provided
        if expected_amount > 0:
            detected_amount = _extract_max_amount(text)
            if detected_amount > 0:
                # Allow if detected amount is at least 50% of expected (partial payments are ok)
                # But reject if it's less than ₹500 or less than 10% of expected
                min_acceptable = max(500, expected_amount * 0.1)
                if detected_amount < min_acceptable:
                    return False, (
                        f"The payment amount detected (₹{detected_amount:,.0f}) seems too low. "
                        f"₹{expected_amount:,} is due. Upload the correct payment screenshot."
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
    """Extract the largest rupee amount found in the text."""
    amounts = []
    # Match ₹X,XXX or Rs.X,XXX patterns
    for match in re.finditer(r'₹\s*([\d,]+(?:\.\d{1,2})?)', text):
        try:
            amounts.append(float(match.group(1).replace(',', '')))
        except ValueError:
            pass
    for match in re.finditer(r'[Rr][Ss]\.?\s*([\d,]+(?:\.\d{1,2})?)', text):
        try:
            amounts.append(float(match.group(1).replace(',', '')))
        except ValueError:
            pass
    # Also match standalone large numbers near payment keywords
    for match in re.finditer(r'(\d{1,3}(?:,\d{3})*(?:\.\d{1,2})?)', text):
        try:
            val = float(match.group(1).replace(',', ''))
            if val >= 100:  # Only consider amounts >= ₹100
                amounts.append(val)
        except ValueError:
            pass
    return max(amounts) if amounts else 0


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
