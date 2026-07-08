"""Ollama vision model integration for interview invite screenshot extraction.

Enhances the existing slot_screenshot_parse.py with AI-powered extraction
using Ollama models running on the developer's laptop (tunneled via SSH).

Primary model: qwen2.5vl:7b (reliable structured extraction)
Backup model: moondream (lightweight fallback)
Falls back to existing OCR only if both AI models fail.

Hybrid flow (fast path):
  1. OCR image → raw text (Tesseract, instant)
  2. If OCR finds date+time, send raw text to qwen2.5:7b text model for JSON cleanup (fast, ~10s)
  3. Only if OCR fails, call qwen2.5vl:7b vision model (slow, ~5 min)
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
OLLAMA_TEXT_TIMEOUT = int(os.environ.get("OLLAMA_TEXT_TIMEOUT", "60"))

# ── Prompt ──────────────────────────────────────────────────────────────────
INVITE_EXTRACTION_PROMPT = """You are an interview invite screenshot extraction assistant.
Read the uploaded screenshot carefully. It may be from Gmail, Teams, Zoom, Google Calendar, Outlook, WhatsApp, Telegram, or any interview scheduling message.

Return ONLY valid JSON. Do not explain. Do not use markdown. Do not wrap JSON inside code blocks.

IMPORTANT: Today's date is {today}. Use this to resolve relative dates:
- "Tomorrow" means {tomorrow}
- "Today" means {today}
- If only month and day are visible (e.g. "JUL 9"), use the current year {year} unless it would be in the past, then use {year} + 1.

Schema:
{{"candidate_name": "", "candidate_phone": "", "client_name": "", "technology": "", "service_type": "", "interview_round": "", "interview_date": "YYYY-MM-DD", "start_time": "hh:mm AM/PM", "end_time": "hh:mm AM/PM", "timezone": "Asia/Kolkata", "meeting_platform": "", "screenshot_source": "", "meeting_link": "", "attendee_name": "", "confidence_score": 0, "missing_fields": [], "warnings": [], "raw_detected_text": "", "is_payment_screenshot": false, "looks_like_interview_invite": true}}

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
- If end time is not visible and duration is not visible, keep end_time empty. Do not guess end_time.
- If date/time is ambiguous, keep confidence_score below 80.
- screenshot_source is the app the screenshot was taken FROM (WhatsApp, Gmail, Teams, Telegram, etc.)
- meeting_platform is the ACTUAL interview platform (FloCareer, HirePro, Zoom, Teams, Google Meet, BarRaiser, etc.)
- Do NOT confuse screenshot_source with meeting_platform. They are different fields.
- technology should be the job role or tech stack (Java, React JS, Data Engineer, Sr Data Reliability Engineer, etc.)
- Do NOT put meeting platform names in technology field.
- If the screenshot is a payment receipt, UPI screenshot, bank transfer screenshot, transaction proof, or payment confirmation, set is_payment_screenshot=true.
- If it is not an interview invite, set looks_like_interview_invite=false.
- confidence_score must be between 0 and 100."""

def _get_invite_prompt() -> str:
    """Get the invite extraction prompt with today's date filled in."""
    from datetime import datetime, timedelta
    today = datetime.now().strftime("%Y-%m-%d")
    tomorrow = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")
    year = datetime.now().year
    return INVITE_EXTRACTION_PROMPT.format(today=today, tomorrow=tomorrow, year=year)


RETRY_PROMPT = "Your previous response was not valid JSON. Return only valid JSON matching the schema. No markdown. No explanation."

# ── Text cleanup prompt (for qwen2.5:7b text model after OCR) ───────────────
TEXT_CLEANUP_PROMPT = """You are an interview invite text extraction assistant.
The following raw OCR text was extracted from an interview invite screenshot.
Parse it and return ONLY valid JSON. Do not explain. Do not use markdown.

IMPORTANT RULES:
- screenshot_source is the app the screenshot was taken from (WhatsApp, Gmail, Teams, Telegram, etc.)
- meeting_platform is the actual interview platform (FloCareer, HirePro, Zoom, Teams, Google Meet, BarRaiser, etc.)
- Do NOT confuse screenshot_source with meeting_platform.
- technology should be the job role/tech stack (Java, React JS, Data Engineer, Sr Data Reliability Engineer, etc.)
- Do NOT put meeting platform names in technology field.
- If only start_time is visible and no end_time or duration is mentioned, leave end_time empty.
- Convert all times to 12-hour hh:mm AM/PM format.
- Convert all dates to YYYY-MM-DD.
- confidence_score must be between 0 and 100.

Schema:
{"candidate_name": "", "candidate_phone": "", "client_name": "", "technology": "", "service_type": "", "interview_round": "", "interview_date": "YYYY-MM-DD", "start_time": "hh:mm AM/PM", "end_time": "hh:mm AM/PM", "timezone": "Asia/Kolkata", "meeting_platform": "", "screenshot_source": "", "meeting_link": "", "attendee_name": "", "confidence_score": 0, "missing_fields": [], "warnings": [], "raw_detected_text": "", "is_payment_screenshot": false, "looks_like_interview_invite": true}

OCR TEXT:
"""


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
    
    # Remove thinking tags if present (qwen2.5 sometimes adds these)
    text = re.sub(r'<think>.*?</think>', '', text, flags=re.DOTALL).strip()
    
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


def call_ollama_text_model(
    model_name: str,
    prompt: str,
    *,
    timeout: int = OLLAMA_TEXT_TIMEOUT,
) -> str | None:
    """Call Ollama text model (no image) for OCR text cleanup.
    
    Returns the raw text response or None on failure.
    """
    try:
        payload = {
            "model": model_name,
            "messages": [
                {
                    "role": "user",
                    "content": prompt,
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
            logger.warning("Ollama text %s returned %d: %s", model_name, resp.status_code, resp.text[:200])
            return None
        data = resp.json()
        content = data.get("message", {}).get("content", "")
        return content if content else None
    except httpx.TimeoutException:
        logger.warning("Ollama text %s timed out after %ds", model_name, timeout)
        return None
    except Exception as e:
        logger.warning("Ollama text %s error: %s", model_name, e)
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
    extracted.setdefault("screenshot_source", "")
    
    # Do not auto-set end_time — only keep it if explicitly extracted
    # If end_time was not in the original extraction, leave it empty
    
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
        "screenshot_source": "",
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
    """Extract interview invite details using hybrid OCR + AI approach.
    
    Hybrid flow (optimized for speed):
      1. OCR image → raw text (Tesseract, instant)
      2. If OCR gets enough text, send to qwen2.5:7b text model for JSON cleanup (~10-30s)
      3. Only if OCR fails or text cleanup fails, call qwen2.5vl:7b vision model (~5 min)
      4. If vision fails, try moondream backup
      5. If all AI fails, fall back to regex OCR parsing
    
    Ollama runs on the developer's laptop, tunneled to VPS via SSH.
    """
    # Check if Ollama is reachable (tunnel must be active)
    if not _is_ollama_available():
        logger.info("Ollama not reachable (SSH tunnel may be down), falling back to OCR")
        return _fallback_to_existing_ocr(image_data, mime_type)
    
    # ── Step 1: Try OCR + text model (fast path) ────────────────────────────
    ocr_text = _run_tesseract_ocr(image_data)
    
    if ocr_text and len(ocr_text) > 10:
        logger.info("OCR extracted %d chars, trying fast extraction", len(ocr_text))
        
        # Try regex first (instant) — works great for structured invites
        regex_result = None
        try:
            from features.slot_screenshot_parse import parse_invite_text
            regex_result = parse_invite_text(ocr_text)
        except Exception as e:
            logger.warning("Regex parse failed: %s", e)
        
        if regex_result and regex_result.get("date") and regex_result.get("time"):
            # Regex found date+time — use it directly, optionally enhance with text model
            logger.info("Regex found date=%s time=%s, using fast path", regex_result["date"], regex_result["time"])
            
            # Build result from regex (instant)
            result = _empty_extraction()
            result["extraction_source"] = "ocr_ai_cleanup"
            result["primary_model"] = "tesseract+regex"
            result["backup_model"] = OLLAMA_REASONING_MODEL
            result["detected_by"] = "OCR + regex"
            result["extraction_method"] = "hybrid_fast"
            result["interview_date"] = regex_result.get("date", "")
            result["start_time"] = normalize_time_to_12h(regex_result.get("time", ""))
            result["end_time"] = normalize_time_to_12h(regex_result.get("time_end", ""))
            result["interview_round"] = regex_result.get("interview_round", "")
            result["meeting_platform"] = regex_result.get("platform", "")
            result["technology"] = regex_result.get("technology", "")
            result["looks_like_interview_invite"] = True
            fields_found = sum(1 for f in ["interview_date", "start_time", "interview_round", "meeting_platform"] if result.get(f))
            result["confidence_score"] = min(92, fields_found * 25 + 10)
            result["missing_fields"] = [f for f in ["interview_date", "start_time", "interview_round"] if not result.get(f)]
            result["manual_fields_required"] = bool(result["missing_fields"])
            result = validate_invite_extraction(result)
            return result
        
        # Regex didn't find date+time — try text model (slower but more capable)
        logger.info("Regex didn't find date/time, trying text model")
        extracted = _try_text_model_cleanup(ocr_text)
        if extracted:
            extracted = validate_invite_extraction(extracted)
            if extracted.get("interview_date") and extracted.get("start_time"):
                extracted["extraction_source"] = "ocr_ai_cleanup"
                extracted["primary_model"] = OLLAMA_REASONING_MODEL
                extracted["backup_model"] = ""
                extracted["detected_by"] = f"OCR + {OLLAMA_REASONING_MODEL}"
                extracted["extraction_method"] = "hybrid_fast"
                logger.info("Text model succeeded: date=%s time=%s", extracted["interview_date"], extracted["start_time"])
                return extracted
    else:
        logger.info("OCR text too short (%d chars), going to vision model", len(ocr_text or ""))
    
    # ── Step 2: Try vision model (slow path) ────────────────────────────────
    img_b64 = base64.b64encode(image_data).decode("utf-8")
    
    logger.info("Calling vision model: %s (timeout=%ds)", OLLAMA_VISION_MODEL, OLLAMA_TIMEOUT)
    start = time.time()
    response = call_ollama_vision_model(
        OLLAMA_VISION_MODEL, img_b64, _get_invite_prompt(), timeout=OLLAMA_TIMEOUT
    )
    elapsed = time.time() - start
    logger.info("Vision model responded in %.1fs", elapsed)
    
    extracted = None
    used_model = OLLAMA_VISION_MODEL
    
    if response:
        extracted = parse_strict_json_response(response)
        if not extracted:
            logger.info("Invalid JSON from vision, retrying...")
            extracted = retry_invalid_json_once(OLLAMA_VISION_MODEL, img_b64, response)
    
    # ── Step 3: If vision failed, try backup model (moondream) ──────────────
    if not extracted:
        logger.warning("Vision model (%s) failed, trying backup: %s", OLLAMA_VISION_MODEL, OLLAMA_BACKUP_VISION_MODEL)
        backup_response = call_ollama_vision_model(
            OLLAMA_BACKUP_VISION_MODEL, img_b64, _get_invite_prompt(), timeout=OLLAMA_TIMEOUT
        )
        if backup_response:
            extracted = parse_strict_json_response(backup_response)
            if extracted:
                used_model = OLLAMA_BACKUP_VISION_MODEL
    
    # ── Step 4: If all AI failed, fall back to regex OCR ────────────────────
    if not extracted:
        logger.warning("All AI models failed, falling back to OCR")
        return _fallback_to_existing_ocr(image_data, mime_type)
    
    # Validate and normalize
    extracted = validate_invite_extraction(extracted)
    
    # Add metadata
    extracted["extraction_source"] = "ollama"
    extracted["primary_model"] = used_model
    extracted["backup_model"] = OLLAMA_BACKUP_VISION_MODEL
    extracted["detected_by"] = used_model
    extracted["extraction_method"] = "vision"
    
    return extracted


def _run_tesseract_ocr(image_data: bytes) -> str:
    """Run Tesseract OCR on image and return raw text."""
    try:
        from features.slot_screenshot_parse import _local_ocr_text
        return _local_ocr_text(image_data)
    except Exception as e:
        logger.warning("Tesseract OCR failed: %s", e)
        return ""


def _try_text_model_cleanup(ocr_text: str) -> dict[str, Any] | None:
    """Send OCR text to qwen2.5:7b text model for structured JSON extraction."""
    from datetime import datetime
    today = datetime.now().strftime("%Y-%m-%d")
    tomorrow = (datetime.now() + __import__('datetime').timedelta(days=1)).strftime("%Y-%m-%d")
    
    date_context = f"\n\nIMPORTANT: Today's date is {today}. If the text says 'Tomorrow', use {tomorrow}. If it says 'Today', use {today}. Resolve all relative dates to absolute YYYY-MM-DD format.\n\nOCR TEXT:\n"
    prompt = TEXT_CLEANUP_PROMPT.rsplit("OCR TEXT:\n", 1)[0] + date_context + ocr_text[:3000]
    
    response = call_ollama_text_model(OLLAMA_REASONING_MODEL, prompt, timeout=OLLAMA_TEXT_TIMEOUT)
    if not response:
        return None
    
    extracted = parse_strict_json_response(response)
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

