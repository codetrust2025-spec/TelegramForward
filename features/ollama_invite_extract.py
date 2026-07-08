"""Ollama vision model integration for interview invite screenshot extraction.

Enhances the existing slot_screenshot_parse.py with AI-powered extraction
using Ollama models running on the developer's laptop (tunneled via SSH).

Primary model: qwen2.5vl:7b (reliable structured extraction)
Backup model: moondream (lightweight fallback)
Falls back to existing OCR only if both AI models fail.
"""
from __future__ import annotations

import base64
import json
import os
import re
import time
import logging
from typing import Any

import httpx

logger = logging.getLogger(__name__)

# ── Configuration ───────────────────────────────────────────────────────────
OLLAMA_BASE_URL = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_VISION_MODEL = os.environ.get("OLLAMA_VISION_MODEL", "qwen2.5vl:7b")
OLLAMA_BACKUP_VISION_MODEL = os.environ.get("OLLAMA_BACKUP_VISION_MODEL", "moondream")
OLLAMA_REASONING_MODEL = os.environ.get("OLLAMA_REASONING_MODEL", "qwen2.5:7b")
OLLAMA_TIMEOUT = int(os.environ.get("OLLAMA_TIMEOUT", "900"))

# ── Prompt ──────────────────────────────────────────────────────────────────
INVITE_EXTRACTION_PROMPT = """You are an interview invite screenshot extraction assistant.
Read the uploaded screenshot carefully. It may be from Gmail, Teams, Zoom, Google Calendar, Outlook, WhatsApp, Telegram, or any interview scheduling message.

Return ONLY valid JSON. Do not explain. Do not use markdown. Do not wrap JSON inside code blocks.

Schema:
{"candidate_name": "", "candidate_phone": "", "client_name": "", "technology": "", "service_type": "", "interview_round": "", "interview_date": "YYYY-MM-DD", "start_time": "hh:mm AM/PM", "end_time": "hh:mm AM/PM", "timezone": "Asia/Kolkata", "meeting_platform": "", "meeting_link": "", "attendee_name": "", "confidence_score": 0, "missing_fields": [], "warnings": [], "raw_detected_text": "", "is_payment_screenshot": false, "looks_like_interview_invite": true}

Rules:
- Extract only visible information.
- Do not guess.
- If a field is not visible, keep it empty.
- Add missing required fields to missing_fields.
- Required booking fields are interview_date, start_time, and interview_round.
- Convert all dates to YYYY-MM-DD.
- Convert all times to 12-hour hh:mm AM/PM format only.
- Never return 24-hour time.
- If screenshot shows 14:30, return 02:30 PM.
- If screenshot shows 19:45, return 07:45 PM.
- If screenshot shows 09:00, return 09:00 AM.
- If screenshot shows 11 AM, return 11:00 AM.
- If screenshot shows 7 PM, return 07:00 PM.
- If end time is not visible but duration is visible, calculate end_time in 12-hour hh:mm AM/PM format and add warning.
- If end time is not visible and duration is also not visible, keep end_time empty.
- If date/time is ambiguous, keep confidence_score below 80.
- If the screenshot is a payment receipt, UPI screenshot, bank transfer screenshot, transaction proof, or payment confirmation, set is_payment_screenshot=true.
- If it is not an interview invite, set looks_like_interview_invite=false.
- confidence_score must be between 0 and 100."""

RETRY_PROMPT = "Your previous response was not valid JSON. Return only valid JSON matching the schema. No markdown. No explanation."


# ── Time normalization ──────────────────────────────────────────────────────
def normalize_time_to_12h(time_value: str) -> str:
    """Convert any time format to 12-hour hh:mm AM/PM format.
    
    Examples:
        00:00 -> 12:00 AM
        09:00 -> 09:00 AM
        11:30 -> 11:30 AM
        12:00 -> 12:00 PM
        14:30 -> 02:30 PM
        19:45 -> 07:45 PM
        23:15 -> 11:15 PM
        7 PM -> 07:00 PM
        7:30 pm -> 07:30 PM
        11:00 AM -> 11:00 AM
    """
    if not time_value or not time_value.strip():
        return ""
    
    val = time_value.strip()
    
    # Already in 12h format? (e.g., "11:00 AM", "02:30 PM")
    match_12h = re.match(r'^(\d{1,2}):(\d{2})\s*(AM|PM|am|pm)$', val)
    if match_12h:
        h, m, ap = int(match_12h.group(1)), int(match_12h.group(2)), match_12h.group(3).upper()
        return f"{h:02d}:{m:02d} {ap}"
    
    # Short 12h format (e.g., "7 PM", "11 AM")
    match_short = re.match(r'^(\d{1,2})\s*(AM|PM|am|pm)$', val)
    if match_short:
        h, ap = int(match_short.group(1)), match_short.group(2).upper()
        return f"{h:02d}:00 {ap}"
    
    # 24-hour format (e.g., "14:30", "09:00", "7:30")
    match_24h = re.match(r'^(\d{1,2}):(\d{2})$', val)
    if match_24h:
        h, m = int(match_24h.group(1)), int(match_24h.group(2))
        if h == 0:
            return f"12:{m:02d} AM"
        elif h < 12:
            return f"{h:02d}:{m:02d} AM"
        elif h == 12:
            return f"12:{m:02d} PM"
        else:
            return f"{h - 12:02d}:{m:02d} PM"
    
    # HH:MM format with AM/PM stuck together (e.g., "2:30PM")
    match_stuck = re.match(r'^(\d{1,2}):(\d{2})(AM|PM|am|pm)$', val)
    if match_stuck:
        h, m, ap = int(match_stuck.group(1)), int(match_stuck.group(2)), match_stuck.group(3).upper()
        return f"{h:02d}:{m:02d} {ap}"
    
    return val  # Return as-is if can't parse


def validate_12h_time_format(time_value: str) -> bool:
    """Check if a time string is valid 12-hour format."""
    if not time_value:
        return False
    return bool(re.match(r'^\d{2}:\d{2}\s(AM|PM)$', time_value))


# ── Ollama API calls ────────────────────────────────────────────────────────
def _is_ollama_available() -> bool:
    """Check if Ollama is running and accessible."""
    try:
        resp = httpx.get(f"{OLLAMA_BASE_URL}/api/tags", timeout=5)
        return resp.status_code == 200
    except Exception:
        return False


def call_ollama_vision_model(
    model_name: str,
    image_base64: str,
    prompt: str,
    *,
    timeout: int = OLLAMA_TIMEOUT,
) -> str | None:
    """Call Ollama vision model with an image and prompt.
    
    Returns the raw text response or None on failure.
    """
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
        if resp.status_code != 200:
            logger.warning("Ollama %s returned %d: %s", model_name, resp.status_code, resp.text[:200])
            return None
        data = resp.json()
        content = data.get("message", {}).get("content", "")
        return content if content else None
    except httpx.TimeoutException:
        logger.warning("Ollama %s timed out after %ds", model_name, timeout)
        return None
    except Exception as e:
        logger.warning("Ollama %s error: %s", model_name, e)
        return None


def parse_strict_json_response(response_text: str) -> dict[str, Any] | None:
    """Parse JSON from model response, handling common issues."""
    if not response_text:
        return None
    
    text = response_text.strip()
    
    # Remove markdown code fences if present
    if text.startswith("```"):
        lines = text.split("\n")
        # Remove first line (```json or ```)
        lines = lines[1:]
        # Remove last line if it's ```
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        text = "\n".join(lines).strip()
    
    # Try direct parse
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    
    # Try to find JSON object in the text
    start = text.find("{")
    end = text.rfind("}")
    if start >= 0 and end > start:
        try:
            return json.loads(text[start:end + 1])
        except json.JSONDecodeError:
            pass
    
    return None


def retry_invalid_json_once(
    model_name: str,
    image_base64: str,
    original_response: str,
) -> dict[str, Any] | None:
    """Retry with a correction prompt if first response was invalid JSON."""
    response = call_ollama_vision_model(
        model_name,
        image_base64,
        RETRY_PROMPT,
    )
    if response:
        return parse_strict_json_response(response)
    return None


def validate_invite_extraction(extracted: dict[str, Any]) -> dict[str, Any]:
    """Validate and normalize the extracted data."""
    if not extracted:
        return _empty_extraction()
    
    # Normalize times to 12h format
    if extracted.get("start_time"):
        extracted["start_time"] = normalize_time_to_12h(extracted["start_time"])
    if extracted.get("end_time"):
        extracted["end_time"] = normalize_time_to_12h(extracted["end_time"])
    
    # Ensure confidence_score is an integer 0-100
    score = extracted.get("confidence_score", 0)
    try:
        score = max(0, min(100, int(score)))
    except (ValueError, TypeError):
        score = 0
    extracted["confidence_score"] = score
    
    # Check required fields
    missing = []
    if not extracted.get("interview_date"):
        missing.append("interview_date")
    if not extracted.get("start_time"):
        missing.append("start_time")
    if not extracted.get("interview_round"):
        missing.append("interview_round")
    extracted["missing_fields"] = missing
    
    # Determine if manual fields are needed
    extracted["manual_fields_required"] = bool(missing) or score < 70
    
    # Ensure boolean fields
    extracted.setdefault("is_payment_screenshot", False)
    extracted.setdefault("looks_like_interview_invite", True)
    extracted.setdefault("warnings", [])
    
    return extracted


def detect_payment_screenshot_from_ai(extracted: dict[str, Any]) -> bool:
    """Check if the AI detected this as a payment screenshot."""
    return bool(extracted.get("is_payment_screenshot"))


def compare_primary_backup_extractions(
    primary: dict[str, Any],
    backup: dict[str, Any],
) -> dict[str, Any]:
    """Compare primary and backup model outputs. Return merged result with warnings."""
    if not backup:
        return primary
    
    warnings = list(primary.get("warnings", []))
    conflicts = []
    
    # Compare key fields
    for field in ("interview_date", "start_time", "end_time", "interview_round", "meeting_platform"):
        p_val = (primary.get(field) or "").strip()
        b_val = (backup.get(field) or "").strip()
        if p_val and b_val and p_val.lower() != b_val.lower():
            conflicts.append(field)
    
    if conflicts:
        warnings.append("AI found conflicting invite details. Please verify manually.")
        # Lower confidence when models disagree
        primary["confidence_score"] = min(primary.get("confidence_score", 0), 75)
        primary["manual_fields_required"] = True
    
    primary["warnings"] = warnings
    return primary


def _empty_extraction() -> dict[str, Any]:
    """Return empty extraction result."""
    return {
        "candidate_name": "",
        "candidate_phone": "",
        "client_name": "",
        "technology": "",
        "service_type": "",
        "interview_round": "",
        "interview_date": "",
        "start_time": "",
        "end_time": "",
        "timezone": "Asia/Kolkata",
        "meeting_platform": "",
        "meeting_link": "",
        "attendee_name": "",
        "confidence_score": 0,
        "missing_fields": ["interview_date", "start_time", "interview_round"],
        "warnings": [],
        "raw_detected_text": "",
        "is_payment_screenshot": False,
        "looks_like_interview_invite": False,
        "manual_fields_required": True,
    }


# ── Main extraction function ────────────────────────────────────────────────
def extract_interview_invite_with_ollama(
    image_data: bytes,
    mime_type: str = "image/jpeg",
) -> dict[str, Any]:
    """Extract interview invite details using Ollama vision models.
    
    Flow:
      1. Try qwen2.5vl:7b (primary) with full OLLAMA_TIMEOUT (900s).
      2. If primary fails/times out, try moondream (backup).
      3. Only fall back to OCR if BOTH AI models fail.
    
    Ollama runs on the developer's laptop, tunneled to VPS via SSH.
    """
    # Check if Ollama is reachable (tunnel must be active)
    if not _is_ollama_available():
        logger.info("Ollama not reachable (SSH tunnel may be down), falling back to OCR")
        return _fallback_to_existing_ocr(image_data, mime_type)
    
    # Encode image to base64
    img_b64 = base64.b64encode(image_data).decode("utf-8")
    
    # ── Step 1: Try primary model (qwen2.5vl:7b) with full timeout ──────────
    logger.info("Calling primary model: %s (timeout=%ds)", OLLAMA_VISION_MODEL, OLLAMA_TIMEOUT)
    start = time.time()
    response = call_ollama_vision_model(
        OLLAMA_VISION_MODEL, img_b64, INVITE_EXTRACTION_PROMPT, timeout=OLLAMA_TIMEOUT
    )
    elapsed = time.time() - start
    logger.info("Primary model responded in %.1fs", elapsed)
    
    extracted = None
    used_model = OLLAMA_VISION_MODEL
    
    if response:
        extracted = parse_strict_json_response(response)
        if not extracted:
            # Retry once for invalid JSON
            logger.info("Invalid JSON from primary, retrying...")
            extracted = retry_invalid_json_once(OLLAMA_VISION_MODEL, img_b64, response)
    
    # ── Step 2: If primary failed, try backup model (moondream) ─────────────
    if not extracted:
        logger.warning("Primary model (%s) failed, trying backup: %s", OLLAMA_VISION_MODEL, OLLAMA_BACKUP_VISION_MODEL)
        backup_response = call_ollama_vision_model(
            OLLAMA_BACKUP_VISION_MODEL, img_b64, INVITE_EXTRACTION_PROMPT, timeout=OLLAMA_TIMEOUT
        )
        if backup_response:
            extracted = parse_strict_json_response(backup_response)
            if extracted:
                used_model = OLLAMA_BACKUP_VISION_MODEL
    
    # ── Step 3: If both AI models failed, fall back to OCR ──────────────────
    if not extracted:
        logger.warning("Both AI models failed, falling back to OCR")
        return _fallback_to_existing_ocr(image_data, mime_type)
    
    # Validate and normalize
    extracted = validate_invite_extraction(extracted)
    
    # Add metadata
    extracted["extraction_source"] = "ollama"
    extracted["primary_model"] = used_model
    extracted["backup_model"] = OLLAMA_BACKUP_VISION_MODEL
    extracted["detected_by"] = used_model
    
    return extracted


def _fallback_to_existing_ocr(image_data: bytes, mime_type: str) -> dict[str, Any]:
    """Fall back to existing OCR parsing when Ollama is unavailable."""
    try:
        from features.slot_screenshot_parse import parse_invite_screenshot
        
        parsed = parse_invite_screenshot(image_data, mime_type)
        
        # Convert existing OCR output to our format
        result = _empty_extraction()
        result["extraction_source"] = "ocr_fallback"
        result["primary_model"] = "tesseract"
        result["backup_model"] = ""
        result["interview_date"] = parsed.get("date", "")
        result["start_time"] = normalize_time_to_12h(parsed.get("time", ""))
        result["end_time"] = normalize_time_to_12h(parsed.get("time_end", ""))
        result["interview_round"] = parsed.get("interview_round", "")
        result["meeting_platform"] = parsed.get("platform", "")
        result["technology"] = parsed.get("technology", "")
        result["looks_like_interview_invite"] = True
        result["warnings"] = ["AI extraction unavailable. Using standard OCR/manual entry."]
        
        # Calculate confidence based on what was detected
        fields_found = sum(1 for f in ["interview_date", "start_time", "interview_round"] if result.get(f))
        result["confidence_score"] = min(85, fields_found * 30)
        result["missing_fields"] = [f for f in ["interview_date", "start_time", "interview_round"] if not result.get(f)]
        result["manual_fields_required"] = bool(result["missing_fields"])
        
        return result
    except Exception as e:
        logger.warning("Fallback OCR also failed: %s", e)
        result = _empty_extraction()
        result["extraction_source"] = "failed"
        result["warnings"] = ["AI extraction unavailable. Using standard OCR/manual entry."]
        return result
