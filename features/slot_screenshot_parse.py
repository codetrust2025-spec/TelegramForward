"""Extract interview date/time from invite screenshots (vision + regex)."""

from __future__ import annotations

import base64
import json
import logging
import os
import re
import urllib.error
import urllib.request
from datetime import datetime, timedelta
from typing import Any

logger = logging.getLogger(__name__)

_MONTHS = {
    "jan": 1, "january": 1,
    "feb": 2, "february": 2,
    "mar": 3, "march": 3,
    "apr": 4, "april": 4,
    "may": 5,
    "jun": 6, "june": 6,
    "jul": 7, "july": 7,
    "aug": 8, "august": 8,
    "sep": 9, "sept": 9, "september": 9,
    "oct": 10, "october": 10,
    "nov": 11, "november": 11,
    "dec": 12, "december": 12,
}


def _env_api_key() -> str:
    return (os.getenv("AI_API_KEY") or os.getenv("OPENAI_API_KEY") or "").strip()


def _env_api_base() -> str:
    return (
        os.getenv("AI_API_BASE_URL")
        or os.getenv("OPENAI_BASE_URL")
        or "https://api.openai.com/v1"
    ).rstrip("/")


def _pad2(n: int) -> str:
    return f"{int(n):02d}"


def _to_24h(hour: int, minute: int, ampm: str) -> tuple[int, int]:
    h = int(hour)
    m = int(minute)
    ap = (ampm or "").strip().lower()
    if ap == "pm" and h < 12:
        h += 12
    if ap == "am" and h == 12:
        h = 0
    return h % 24, m % 60


def _fmt_hhmm(h: int, m: int) -> str:
    return f"{_pad2(h)}:{_pad2(m)}"


def _parse_date_token(text: str) -> str:
    """Return YYYY-MM-DD from common invite formats."""
    blob = (text or "").replace("\n", " ")
    iso = re.search(r"\b(20\d{2})-(\d{2})-(\d{2})\b", blob)
    if iso:
        return f"{iso.group(1)}-{iso.group(2)}-{iso.group(3)}"
    slash = re.search(r"\b(\d{1,2})[/.-](\d{1,2})[/.-](20\d{2})\b", blob)
    if slash:
        d, m, y = int(slash.group(1)), int(slash.group(2)), int(slash.group(3))
        if m > 12 and d <= 12:
            d, m = m, d
        return f"{y:04d}-{_pad2(m)}-{_pad2(d)}"
    named = re.search(
        r"\b(\d{1,2})\s*[/\-.]?\s*"
        r"(jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|jun(?:e)?|"
        r"jul(?:y)?|aug(?:ust)?|sep(?:t(?:ember)?)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)"
        r"\s*[/\-.]?\s*(20\d{2})\b",
        blob,
        re.IGNORECASE,
    )
    if named:
        d = int(named.group(1))
        mon = _MONTHS.get(named.group(2).lower()[:3], 0)
        if len(named.group(2)) > 3:
            mon = _MONTHS.get(named.group(2).lower(), mon)
        y = int(named.group(3))
        if mon:
            return f"{y:04d}-{_pad2(mon)}-{_pad2(d)}"
    named2 = re.search(
        r"\b(jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|jun(?:e)?|"
        r"jul(?:y)?|aug(?:ust)?|sep(?:t(?:ember)?)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)"
        r"\s+(\d{1,2}),?\s+(20\d{2})\b",
        blob,
        re.IGNORECASE,
    )
    if named2:
        mon = _MONTHS.get(named2.group(1).lower()[:3], 0)
        if len(named2.group(1)) > 3:
            mon = _MONTHS.get(named2.group(1).lower(), mon)
        d = int(named2.group(2))
        y = int(named2.group(3))
        if mon:
            return f"{y:04d}-{_pad2(mon)}-{_pad2(d)}"
    return ""


def _parse_time_token(match: re.Match) -> tuple[int, int]:
    h = int(match.group(1))
    m = int(match.group(2)) if match.lastindex and match.group(2) and match.group(2).isdigit() else 0
    ampm = ""
    for g in match.groups():
        if g and str(g).lower() in {"am", "pm"}:
            ampm = str(g).lower()
            break
    return _to_24h(h, m, ampm)


def _parse_times_from_blob(blob: str) -> tuple[str, str]:
    text = (blob or "").lower().replace("–", "-").replace("—", "-")
    range_pat = re.compile(
        r"\b(\d{1,2})(?::(\d{2}))?\s*(am|pm)?\s*"
        r"(?:-|to|–|—)\s*"
        r"(\d{1,2})(?::(\d{2}))?\s*(am|pm)\b",
        re.IGNORECASE,
    )
    m = range_pat.search(text)
    if m:
        sh, sm = _to_24h(int(m.group(1)), int(m.group(2) or 0), m.group(3) or m.group(6))
        eh, em = _to_24h(int(m.group(4)), int(m.group(5) or 0), m.group(6))
        if (eh, em) <= (sh, sm) and (m.group(3) or "").lower() == "pm" and not (m.group(6) or "").lower():
            eh += 12 if eh < 12 else 0
        return _fmt_hhmm(sh, sm), _fmt_hhmm(eh, em)
    colon = re.search(r"\b(\d{1,2}):(\d{2})\s*(am|pm)\b", text, re.IGNORECASE)
    if colon:
        sh, sm = _to_24h(int(colon.group(1)), int(colon.group(2)), colon.group(3))
        end_total = sh * 60 + sm + 30
        return _fmt_hhmm(sh, sm), _fmt_hhmm(end_total // 60, end_total % 60)
    plain = re.search(r"(?<![:\d])\b(\d{1,2})\s*(am|pm)\b", text, re.IGNORECASE)
    if plain:
        sh, sm = _to_24h(int(plain.group(1)), 0, plain.group(2))
        end_total = sh * 60 + sm + 30
        return _fmt_hhmm(sh, sm), _fmt_hhmm(end_total // 60, end_total % 60)
    return "", ""


def _parse_round_from_blob(blob: str) -> str:
    text = (blob or "").upper()
    for label in ("L4", "L3", "L2", "L1", "HR", "FINAL", "SCREENING"):
        if re.search(rf"\b{label}\b", text):
            return "Final" if label == "FINAL" else ("Screening" if label == "SCREENING" else label)
    if re.search(r"\bTECHNICAL\b", text):
        return "L1"
    return ""


def _parse_platform_from_blob(blob: str) -> str:
    low = (blob or "").lower()
    if "microsoft teams" in low or "teams meeting" in low:
        return "teams"
    if "zoom" in low:
        return "zoom"
    if "google calendar" in low or "calendar invite" in low:
        return "google_calendar"
    if "gmail" in low or "google meet" in low:
        return "gmail"
    if "barraiser" in low:
        return "barraiser"
    return ""


def parse_invite_text(blob: str) -> dict[str, Any]:
    """Regex extraction from OCR or vision text."""
    date = _parse_date_token(blob)
    start, end = _parse_times_from_blob(blob)
    return {
        "date": date,
        "time": start,
        "time_end": end,
        "interview_round": _parse_round_from_blob(blob),
        "technology": "",
        "platform": _parse_platform_from_blob(blob),
        "raw_text": (blob or "")[:2000],
    }


def _vision_extract_json(data: bytes, mime: str) -> dict[str, Any]:
    api_key = _env_api_key()
    if not api_key:
        return {}
    b64 = base64.b64encode(data).decode("ascii")
    safe_mime = mime if mime.startswith("image/") else "image/jpeg"
    prompt = (
        "Read this interview invite / calendar / Teams / Zoom / Gmail screenshot. "
        "Return JSON only with keys: date (YYYY-MM-DD), time (HH:MM 24h), "
        "time_end (HH:MM 24h), interview_round (L1|L2|HR|Final|Screening or empty), "
        "technology (short stack or empty), platform (teams|zoom|gmail|google_calendar|barraiser|other). "
        "Use India timezone if shown. If only one time, set time_end 30 minutes after time."
    )
    payload = {
        "model": os.getenv("SLOT_PARSE_VISION_MODEL", "gpt-4o-mini"),
        "messages": [{
            "role": "user",
            "content": [
                {"type": "text", "text": prompt},
                {"type": "image_url", "image_url": {"url": f"data:{safe_mime};base64,{b64}"}},
            ],
        }],
        "max_tokens": 280,
        "temperature": 0,
        "response_format": {"type": "json_object"},
    }
    req = urllib.request.Request(
        f"{_env_api_base()}/chat/completions",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=35) as resp:
            body = json.loads(resp.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        logger.warning("slot screenshot vision failed: %s", exc)
        return {}
    try:
        content = (body.get("choices") or [{}])[0].get("message", {}).get("content") or "{}"
        parsed = json.loads(content)
        return parsed if isinstance(parsed, dict) else {}
    except (json.JSONDecodeError, TypeError, IndexError):
        return {}


def _norm_time_field(val: str) -> str:
    raw = (val or "").strip()
    if not raw:
        return ""
    if re.match(r"^\d{2}:\d{2}$", raw):
        return raw
    start, _ = _parse_times_from_blob(raw)
    return start or raw


def _merge_parsed(vision: dict[str, Any], regex: dict[str, Any]) -> dict[str, Any]:
    out = {
        "date": "",
        "time": "",
        "time_end": "",
        "interview_round": "",
        "technology": "",
        "platform": "",
        "raw_text": regex.get("raw_text") or "",
    }
    for key in out:
        if key == "raw_text":
            continue
        val = str(vision.get(key) or "").strip()
        if not val:
            val = str(regex.get(key) or "").strip()
        out[key] = val
    out["date"] = _parse_date_token(out["date"]) or out["date"]
    out["time"] = _norm_time_field(out["time"])
    out["time_end"] = _norm_time_field(out["time_end"])
    if out["time"] and not out["time_end"]:
        try:
            sh, sm = map(int, out["time"].split(":")[:2])
            total = sh * 60 + sm + 30
            out["time_end"] = _fmt_hhmm(total // 60, total % 60)
        except ValueError:
            pass
    return out


def parse_invite_screenshot(data: bytes, mime: str = "image/jpeg") -> dict[str, Any]:
    """
    Parse invite screenshot → slot fields.
    Raises ValueError when date/time cannot be determined.
    """
    if not data:
        raise ValueError("Screenshot file is empty")
    if len(data) > 8 * 1024 * 1024:
        raise ValueError("Screenshot must be under 8 MB")

    vision = _vision_extract_json(data, mime)
    regex_blob = " ".join(
        str(v) for v in vision.values() if isinstance(v, str) and v.strip()
    )
    regex = parse_invite_text(regex_blob)
    merged = _merge_parsed(vision, regex)

    from features.candidate_store import canonical_technology, normalise_interview_round

    merged["interview_round"] = normalise_interview_round(merged.get("interview_round"))
    tech = canonical_technology(merged.get("technology") or "")
    if tech and tech not in {"", "Unspecified"}:
        merged["technology"] = tech
    else:
        merged["technology"] = ""

    if not merged.get("date") or not merged.get("time"):
        raise ValueError(
            "Could not read date and time from the screenshot — "
            "use a clear invite image (Teams, Gmail, Calendar, Zoom)."
        )
    merged["parsed"] = True
    merged["method"] = "vision" if vision else "regex"
    return merged
