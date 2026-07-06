"""Persistent storage for the Candidates / Profiles tracker.

This replaces the old Google Sheet ("Profiles list update Form"). Every row
that used to live in the sheet is now a record in `data/candidates.json` and
is editable directly from the dashboard.

Schema (one row):

    {
        "id":            "auto-generated short id (string)",
        "name":          "candidate full name",
        "stage":         "in_progress | completed | fail | dropped",
        "technology":    "SAP BASIS | React JS | AWS Admin | ..." (free text),
        "task":          "not_started | in_progress | decision_need | completed",
        "phone":         "10-digit Indian phone or international",
        "reference":     "who referred the lead (free text)",
        "payment":       <int> rupees (0 if blank),
        "date":          "YYYY-MM-DD" (interview slot day when slot_confirmed; else lead logged date),
        "logged_date":   "YYYY-MM-DD" (when the lead was first logged — never overwritten by slot assign),
        "time":          "HH:MM" 24h (blank ok),
        "time_end":      "HH:MM" 24h interview slot end (blank ok),
        "slot_confirmed": false until owner + initial payment (handler workspace rule),
        "slot_confirmed_at": ISO timestamp when slot was confirmed (blank ok),
        "slots_group_posted": true after slot screenshot posted in Interview slots WA group,
        "interview_attendee": "Nikhila | Bhavana | Tool — who supported the live interview (set when marking attendance)",
        "interview_attendance_status": "attended | not_attended | cancelled | rescheduled | blank (pending)",
        "interview_attendance_remark": "optional note when logging attendance",
        "interview_attended": legacy bool — true when status is attended,
        "interview_attended_at": ISO timestamp when attendance was logged,
        "interview_attended_by": handler name who logged attendance,
        "purpose":       "interview_support | work_support | experience_docs | other (Excel PURPOSE column)",
        "expenses":      "free text — e.g. '12000 GYM', '3000 fuel' (was 'Expenses PAVAN')",
        "notes":         "free text — any extra context",
        "created_at":    ISO timestamp (set on insert),
        "updated_at":    ISO timestamp (set on every patch),
    }

Everything is intentionally JSON-on-disk with a coarse lock so it matches
the rest of the project (`crm/leads.json`, `ai_smart_reply.json`, etc.).
"""
from __future__ import annotations

import json
import os
import re
import time
import uuid
from datetime import datetime, timedelta, timezone
from threading import Lock

from core.config import DATA_DIR

_FILE = os.path.join(DATA_DIR, "candidates.json")
# Each candidate gets its own folder under here so we never accidentally
# mix screenshots between people, even if filenames collide.
PROOFS_DIR = os.path.join(DATA_DIR, "candidates_proofs")
RESUMES_DIR = os.path.join(DATA_DIR, "candidates_resumes")
_lock = Lock()
_load_cache: dict | None = None
_load_cache_at: float = 0.0
_LOAD_CACHE_TTL = 15.0  # seconds — avoids repeated PG reads per dashboard refresh

# Allowed image MIME types for payment-proof uploads. We deliberately
# keep this short — the dashboard is meant for screenshots / receipts,
# not arbitrary file uploads.
_ALLOWED_MIME = {
    "image/jpeg": "jpg",
    "image/jpg":  "jpg",
    "image/png":  "png",
    "image/webp": "webp",
    "image/gif":  "gif",
    "image/heic": "heic",
    "image/heif": "heif",
}
_ALLOWED_RESUME_MIME = {
    "application/pdf": "pdf",
    "application/msword": "doc",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": "docx",
    "text/plain": "txt",
}
MAX_PROOF_BYTES = 8 * 1024 * 1024  # 8 MB per screenshot
MAX_RESUME_BYTES = 10 * 1024 * 1024  # 10 MB per resume file

VALID_STAGES = {"in_progress", "completed", "fail", "dropped"}
VALID_TASKS = {"not_started", "in_progress", "decision_need", "completed"}

# Auto-generated screenshot / import placeholders — never store in candidate notes.
_SCREENSHOT_NOTE_NOISE = (
    "microsoft teams — read from screenshot",
    "microsoft teams - read from screenshot",
    "zoom — read from screenshot",
    "zoom - read from screenshot",
    "google calendar — read from screenshot",
    "google calendar - read from screenshot",
    "read from screenshot",
    "manual entry on submit-slot form",
    "candidate screenshot upload",
    "candidate manual slot entry",
    "public-upload",
)


def sanitize_candidate_notes(text: str) -> str:
    """Drop platform/import boilerplate from notes; keep real operator text."""
    raw = (text or "").strip()
    if not raw:
        return ""
    kept: list[str] = []
    for line in raw.splitlines():
        chunk = line.strip()
        if not chunk:
            continue
        lower = chunk.lower()
        if lower in _SCREENSHOT_NOTE_NOISE:
            continue
        for noise in _SCREENSHOT_NOTE_NOISE:
            if noise in lower:
                chunk = re.sub(re.escape(noise), "", chunk, flags=re.IGNORECASE).strip()
                chunk = re.sub(r"^[·\-–—\s]+|[·\-–—\s]+$", "", chunk).strip()
                lower = chunk.lower()
        if chunk and lower not in _SCREENSHOT_NOTE_NOISE:
            kept.append(chunk)
    return "\n".join(kept).strip()


def purge_screenshot_placeholder_notes() -> dict[str, int]:
    """One-shot cleanup: remove stored Teams/screenshot boilerplate from every candidate."""
    data = _load(force=True)
    rows = data.get("candidates") or []
    changed = 0
    for row in rows:
        old = row.get("notes") or ""
        new = sanitize_candidate_notes(old)
        if new != old:
            row["notes"] = new
            row["updated_at"] = _now_iso()
            changed += 1
    if changed:
        data["candidates"] = rows
        _save(data)
    return {"changed": changed, "total": len(rows)}

# Every candidate is expected to pay this much as the baseline onboarding
# amount. Anything less is tracked as a pending balance with a required
# follow-up remark.
#
# Two baselines because we have two acquisition channels:
#   - direct  (default): ₹20,000 per profile
#   - consultancy        : ₹15,000 per profile (consultancy partner already
#                          takes their cut, so we charge the client less)
# A per-candidate boolean `consultancy` flips the default. The operator
# can still override `expected_payment` manually for either path.
DEFAULT_EXPECTED_PAYMENT       = 20_000
CONSULTANCY_EXPECTED_PAYMENT   = 15_000
ROUND_WISE_EXTERNAL_PAYMENT = 5_000
ROUND_WISE_INTERNAL_PAYMENT = 9_000
BGV_CERTIFICATES_PAYMENT = 30_000
# Legacy aliases (domestic/non_domestic → external/internal)
ROUND_WISE_DOMESTIC_PAYMENT = ROUND_WISE_EXTERNAL_PAYMENT
ROUND_WISE_NON_DOMESTIC_PAYMENT = ROUND_WISE_INTERNAL_PAYMENT
# Minimum initial payment before a handler may mark the interview slot confirmed.
PROFILE_SERVICE_SLOT_MIN_PAYMENT = 10_000

VALID_SERVICE_TYPES = {"profile_service", "round_wise"}
VALID_INTERVIEW_SCOPES = {"external", "internal"}
VALID_PURPOSES = {"interview_support", "work_support", "experience_docs", "other"}
VALID_INTERVIEW_ROUNDS = frozenset({
    "L1", "L2", "HR", "Final", "Screening",
})
INTERVIEW_ATTENDANCE_STATUSES = frozenset({
    "attended",
    "not_attended",
    "cancelled",
    "rescheduled",
})


def baseline_for(consultancy: bool) -> int:
    """The default rupee baseline a candidate is expected to pay."""
    return CONSULTANCY_EXPECTED_PAYMENT if consultancy else DEFAULT_EXPECTED_PAYMENT


def baseline_for_service(
    service_type: str,
    *,
    consultancy: bool = False,
    interview_scope: str = "external",
    bgv_certificates: bool = False,
) -> int:
    if service_type == "round_wise":
        scope = _normalise_interview_scope(interview_scope)
        base = (
            ROUND_WISE_INTERNAL_PAYMENT
            if scope == "internal"
            else ROUND_WISE_EXTERNAL_PAYMENT
        )
    else:
        base = baseline_for(consultancy)
    return base + (BGV_CERTIFICATES_PAYMENT if bgv_certificates else 0)

# The referrer (handler) is paid this share of every rupee the client pays
# the business. The operator does not log commissions by hand — they're
# computed from the candidate's `payment` field. The handler_expenses
# ledger now only tracks money already paid OUT (commission disbursements,
# travel, food etc.) — net = auto_earnings − paid_out.
#
# If the referrer charges the client below the prescribed tariff, their
# commission is penalised by the shortfall: basis = max(0, 2×received −
# prescribed), then 50%. Example: internal round prescribed ₹9k, client
# pays ₹5k → basis ₹1k → handler gets ₹500 (not ₹2,500).
HANDLER_COMMISSION_PCT = 50

# Owners / admins — not handler commission recipients (hidden from payout UI).
HANDLER_PAYOUT_EXCLUDED_REF_KEYS = frozenset({"ravinder"})

# Always offered in the Reference dropdown (even before their first lead).
HANDLER_REFERENCE_PRESETS: tuple[str, ...] = (
    "Charan",
    "Ravinder",
)

# WhatsApp interview-slots group — always offer in public submit-slot dropdown.
PUBLIC_SLOT_BOOKER_NAMES: tuple[str, ...] = (
    "Ravali",
    "Gangadhar",
    "Raja Gopal",
    "Vaishnavi",
    "Adivi Satyanarayana",
    "Manu",
    "Keerthana",
    "Ram Charan M S",
    "Abilash Perla",
    "Gopichand",
    "KALESHWAR",
    "Thummala Karunakar",
    "Shailaja",
)

# No longer booking slots via /submit-slot (placed, dropped, etc.).
PUBLIC_SLOT_BOOKING_EXCLUDED: tuple[str, ...] = (
    "Farhana",
)


def prescribed_baseline(row: dict) -> int:
    """Tariff before any manual expected_payment override."""
    consultancy = bool(row.get("consultancy", False))
    service_type = _normalise_service_type(row.get("service_type"), row)
    interview_scope = _normalise_interview_scope(row.get("interview_scope"), row)
    return baseline_for_service(
        service_type,
        consultancy=consultancy,
        interview_scope=interview_scope,
        bgv_certificates=_coerce_bool(row.get("bgv_certificates")),
    )


def effective_expected_payment(row: dict) -> int:
    """Agreed client charge for this row (manual override or prescribed baseline)."""
    if is_free_service_candidate(row.get("name") or ""):
        return 0
    consultancy = bool(row.get("consultancy", False))
    service_type = _normalise_service_type(row.get("service_type"), row)
    interview_scope = _normalise_interview_scope(row.get("interview_scope"), row)
    fallback = baseline_for_service(
        service_type,
        consultancy=consultancy,
        interview_scope=interview_scope,
        bgv_certificates=_coerce_bool(row.get("bgv_certificates")),
    )
    expected = int(row.get("expected_payment") or 0)
    if expected <= 0:
        return fallback
    # Stale direct default (₹20k) on a consultancy profile row — use ₹15k channel baseline.
    if (
        service_type == "profile_service"
        and consultancy
        and expected == DEFAULT_EXPECTED_PAYMENT
    ):
        return CONSULTANCY_EXPECTED_PAYMENT
    return expected


def referrer_commission_basis(row: dict) -> int:
    """Rupee basis for handler commission before the 50% split.

    BGV certificates are billed by a third-party company and are only
    mediated here, so their ₹30k pass-through amount is never commissionable.
    """
    received = int(row.get("payment") or 0)
    if received <= 0:
        return 0
    bgv_charge = BGV_CERTIFICATES_PAYMENT if _coerce_bool(row.get("bgv_certificates")) else 0
    agreed = max(0, effective_expected_payment(row) - bgv_charge)
    charged = min(received, agreed) if agreed > 0 else 0
    prescribed = baseline_for_service(
        _normalise_service_type(row.get("service_type"), row),
        consultancy=bool(row.get("consultancy", False)),
        interview_scope=_normalise_interview_scope(row.get("interview_scope"), row),
    )
    # Installments toward the agreed deal — commission accrues on cash received.
    if agreed > 0 and received < agreed:
        return charged
    if charged < prescribed:
        return max(0, 2 * charged - prescribed)
    return charged


def referrer_commission_amount(row: dict) -> int:
    return (referrer_commission_basis(row) * HANDLER_COMMISSION_PCT) // 100


# ── Helpers ─────────────────────────────────────────────────────────────────

def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def canonical_technology(tech: str) -> str:
    """Merge spelling variants (e.g. React Js vs React JS) for roster grouping."""
    raw = (tech or "").strip()
    if not raw:
        return "Unspecified"
    key = " ".join(raw.lower().replace("_", " ").replace("-", " ").split())
    aliases = {
        "react js": "React JS",
        "reactjs": "React JS",
        "angular": "Angular",
        "angularjs": "Angular",
        "mern stack": "MERN stack",
        "aws devops": "AWS DevOps",
        "automation testing": "Automation Testing",
        "testing": "Testing",
        "etl": "ETL",
        "sap basis": "SAP BASIS",
        "unspecified": "Unspecified",
        "data analyst": "Data Analyst",
    }
    return aliases.get(key, raw)


# Who supported the interview (set when marking attendance).
INTERVIEW_ATTENDEE_NAMES = ("Nikhila", "Bhavana", "Tool")
TOOL_PROFILE_CANDIDATE_TECHNOLOGY = "Data Analyst"


def _normalise_candidate_name_key(name: str) -> str:
    return " ".join((name or "").strip().lower().split())


_CANDIDATE_NAME_ALIASES: dict[str, str] = {
    "perla abhilash": "Abilash Perla",
    "abhilash perla": "Abilash Perla",
    "abilash perla": "Abilash Perla",
    "ram charan m s": "Ram Charan M S",
    "ram charan ms": "Ram Charan M S",
    "reddy charan m s": "Ram Charan M S",
    "ganguli1433": "Gangadhar",
    "ganguli": "Gangadhar",
}


def canonical_candidate_name(name: str) -> str:
    """Single display name per person — e.g. PERLA ABHILASH → Abilash Perla."""
    raw = _clean_str(name)
    if not raw:
        return ""
    key = _normalise_candidate_name_key(raw)
    if key in _CANDIDATE_NAME_ALIASES:
        return _CANDIDATE_NAME_ALIASES[key]
    if "perla" in key and ("abhilash" in key or "abilash" in key):
        return "Abilash Perla"
    if ("ram charan" in key or "reddy charan" in key) and ("m s" in key or key.endswith(" ms")):
        return "Ram Charan M S"
    return raw


def candidate_defaults_to_tool_attendee(name: str) -> bool:
    """Keerthana / Satyanarayana — Tool attends and Data Analyst tech stack."""
    return is_free_service_candidate(name)


def is_free_service_candidate(name: str) -> bool:
    """Complimentary Tool-attended profiles — no client payment expected."""
    key = _normalise_candidate_name_key(name)
    if not key:
        return False
    return "keerthana" in key or "satyanarayana" in key


def is_low_priority_slot_booker(name: str) -> bool:
    """Last-priority bookers via submit-slot — cannot take slots held by others."""
    key = _normalise_candidate_name_key(canonical_candidate_name(name))
    if not key:
        return False
    if "keerthana" in key:
        return True
    if "satyanarayana" in key:
        return True
    if "raja gopal" in key:
        return True
    return False


# Nicknames / WhatsApp handles → substring expected in canonical store name
_CANDIDATE_SEARCH_HINTS: dict[str, tuple[str, ...]] = {
    "satya": ("satyanarayana", "adivi"),
    "keerthana": ("keerthana",),
    "keethana": ("keerthana",),
    "farha": ("farhana",),
    "farhana": ("farhana",),
    "gangadhar": ("gangadhar", "gangadhara"),
    "ganguli": ("gangadhar", "gangadhara"),
    "ravali": ("ravali",),
    "data": ("kaleshwar",),
    "manu": ("manu",),
    "charan": ("ram charan", "reddy charan"),
    "abhilash": ("abilash", "perla"),
    "perla": ("abilash", "perla"),
    "gopi": ("gopichand",),
    "gopichand": ("gopichand",),
    "karunakar": ("karunakar", "thummala"),
    "vaishnavi": ("vaishnavi",),
    "raja": ("raja gopal",),
}


def candidate_matches_search(name: str, query: str) -> bool:
    """True when free-text query matches candidate display name (incl. nicknames)."""
    q = (query or "").strip().lower()
    if not q:
        return True
    n = _normalise_candidate_name_key(name)
    if not n:
        return False
    if q in n:
        return True
    hints = _CANDIDATE_SEARCH_HINTS.get(q)
    if hints:
        return any(h in n for h in hints)
    for part in q.split():
        if len(part) < 2:
            continue
        if part in n:
            return True
        part_hints = _CANDIDATE_SEARCH_HINTS.get(part)
        if part_hints and any(h in n for h in part_hints):
            return True
    return False


def row_candidate_technology(row: dict) -> str:
    stored = canonical_technology(row.get("technology") or "")
    if candidate_defaults_to_tool_attendee(row.get("name") or ""):
        if stored in {"", "Unspecified"}:
            return TOOL_PROFILE_CANDIDATE_TECHNOLOGY
    return stored


def infer_interview_attendee(technology: str = "", name: str = "") -> str:
    if candidate_defaults_to_tool_attendee(name):
        return "Tool"
    return "Bhavana"


def normalise_interview_attendee_name(raw: str | None) -> str:
    key = (raw or "").strip()
    if not key:
        return ""
    canon = _canonical_reference_name(key)
    lowered = canon.lower()
    if lowered == "nikhila":
        return "Nikhila"
    if lowered == "bhavana":
        return "Bhavana"
    if lowered == "tool":
        return "Tool"
    raise ValueError("Interview attendee must be Nikhila, Bhavana, or Tool")


def normalise_interview_attendance_status(
    raw: str | None,
    *,
    legacy_attended: bool | None = None,
) -> str:
    key = (raw or "").strip().lower()
    if key in {"pending", ""}:
        return ""
    if key == "canceled":
        key = "cancelled"
    if key == "reschedule":
        key = "rescheduled"
    if key in INTERVIEW_ATTENDANCE_STATUSES:
        return key
    if legacy_attended is True:
        return "attended"
    return ""


def row_interview_attendance_status(row: dict) -> str:
    stored = (row.get("interview_attendance_status") or "").strip().lower()
    if stored == "canceled":
        stored = "cancelled"
    if stored == "reschedule":
        stored = "rescheduled"
    if stored in INTERVIEW_ATTENDANCE_STATUSES:
        return stored
    if _coerce_bool(row.get("interview_attended")):
        return "attended"
    return ""


def _interview_attendance_counts(rows: list[dict]) -> dict[str, int]:
    attended = 0
    not_attended = 0
    cancelled = 0
    rescheduled = 0
    for row in rows:
        status = row_interview_attendance_status(row)
        if status == "attended":
            attended += 1
        elif status == "not_attended":
            not_attended += 1
        elif status == "cancelled":
            cancelled += 1
        elif status == "rescheduled":
            rescheduled += 1
    pending = max(0, len(rows) - attended - not_attended - cancelled - rescheduled)
    return {
        "attended_count": attended,
        "not_attended_count": not_attended,
        "cancelled_count": cancelled,
        "rescheduled_count": rescheduled,
        "pending_count": pending,
    }


def row_interview_attendee(row: dict) -> str:
    explicit = (row.get("interview_attendee") or "").strip()
    if candidate_defaults_to_tool_attendee(row.get("name") or ""):
        return "Tool"
    if explicit:
        try:
            return normalise_interview_attendee_name(explicit)
        except ValueError:
            # Older imports accidentally copied the referrer into this field.
            # A referrer is never an interview attendee.
            pass
    # Bhavana is the default support attendee for every non-Tool interview.
    return infer_interview_attendee(row.get("technology") or "", row.get("name") or "")


def repair_invalid_interview_attendees() -> int:
    """Replace legacy referrer values in the attendee field with the default."""
    data = _load()
    rows = data.get("candidates") or []
    changed = 0
    for index, raw in enumerate(rows):
        if not _coerce_bool(raw.get("slot_confirmed")):
            continue
        expected = infer_interview_attendee(raw.get("technology") or "", raw.get("name") or "")
        current = _clean_str(raw.get("interview_attendee"))
        try:
            valid = normalise_interview_attendee_name(current) if current else ""
        except ValueError:
            valid = ""
        if valid == expected:
            continue
        row = dict(raw)
        row["interview_attendee"] = expected
        row["updated_at"] = _now_iso()
        rows[index] = row
        changed += 1
    if changed:
        data["candidates"] = rows
        _save(data)
    return changed


def _is_interview_attender_reference(reference: str | None) -> bool:
    key = (reference or "").strip().lower()
    return key in {"bhavana", "nikhila"}


def _technology_key(tech: str) -> str:
    return canonical_technology(tech).lower()


def _new_id() -> str:
    return uuid.uuid4().hex[:10]


def _empty() -> dict:
    return {"candidates": [], "updated_at": None}


def _load(*, force: bool = False) -> dict:
    global _load_cache, _load_cache_at
    import time

    now = time.monotonic()
    if (
        not force
        and _load_cache is not None
        and (now - _load_cache_at) < _LOAD_CACHE_TTL
    ):
        return _load_cache

    from core.db.connection import use_postgres

    if use_postgres():
        from core.db.candidates_pg import pg_load as pg_candidates_load
        data = pg_candidates_load()
        if not data.get("candidates"):
            data = _empty()
        else:
            data.setdefault("updated_at", None)
    else:
        with _lock:
            if not os.path.exists(_FILE):
                data = _empty()
            else:
                try:
                    with open(_FILE, encoding="utf-8") as f:
                        data = json.load(f)
                    if not isinstance(data, dict):
                        data = _empty()
                    else:
                        data.setdefault("candidates", [])
                        data.setdefault("updated_at", None)
                except (OSError, json.JSONDecodeError):
                    data = _empty()

    _load_cache = data
    _load_cache_at = now
    return data


def _save(data: dict) -> None:
    global _load_cache, _load_cache_at
    _load_cache = None
    _load_cache_at = 0.0

    from core.db.connection import use_postgres

    if use_postgres():
        from core.db.candidates_pg import pg_save as pg_candidates_save
        data = dict(data)
        data["updated_at"] = _now_iso()
        pg_candidates_save(data)
        return
    os.makedirs(os.path.dirname(_FILE), exist_ok=True)
    data["updated_at"] = _now_iso()
    with _lock:
        tmp = _FILE + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        os.replace(tmp, _FILE)


def _coerce_payment(value) -> int:
    """Accept '5000', '₹5,000', '₹5,000.00', 5000, 5000.5 — normalise to int rupees."""
    if value is None or value == "":
        return 0
    if isinstance(value, (int, float)):
        return int(value)
    s = str(value).strip().replace("₹", "").replace(",", "").replace(" ", "")
    if not s or s.lower() in {"xx.xx", "nan", "-"}:
        return 0
    try:
        return int(float(s))
    except ValueError:
        return 0


def _clean_str(value, *, default: str = "") -> str:
    if value is None:
        return default
    s = str(value).strip()
    return s or default


def _reference_key(ref: str) -> str:
    """Case-insensitive bucket key for handler / reference names."""
    return (ref or "").strip().lower() or "unknown"


def _reference_matches_scope(ref: str, scope_key: str | None) -> bool:
    if not scope_key:
        return True
    return _reference_key(ref) == scope_key


def _payout_excluded_handler(ref: str) -> bool:
    """Owner/admin accounts — excluded from handler payout totals and recovery UI."""
    return _reference_key(ref) in HANDLER_PAYOUT_EXCLUDED_REF_KEYS


def _canonical_reference_name(ref: str) -> str:
    """Normalize spelling for storage — 'PAVAN KALYAN' → 'Pavan Kalyan'."""
    s = " ".join((ref or "").split()).strip()
    if not s:
        return ""
    if s.lower() == "unknown":
        return "Unknown"
    return s.title()


def _prefer_reference_display(existing: str, new: str) -> str:
    """When the same handler was typed two ways, pick the nicer label."""
    a = (existing or "").strip()
    b = (new or "").strip()
    if not a:
        return _canonical_reference_name(b)
    if not b:
        return a
    if _reference_key(a) != _reference_key(b):
        return a
    a_caps = a == a.upper() and any(c.isalpha() for c in a)
    b_caps = b == b.upper() and any(c.isalpha() for c in b)
    if a_caps and not b_caps:
        return b
    if b_caps and not a_caps:
        return a
    return _canonical_reference_name(a)


def reference_dropdown_names(rows: list[dict] | None = None) -> list[str]:
    """Sorted referrer names for add/edit candidate Reference field."""
    if rows is None:
        rows = list_candidates()
    by_key: dict[str, str] = {}
    for preset in HANDLER_REFERENCE_PRESETS:
        name = _canonical_reference_name(preset)
        if name:
            by_key[_reference_key(name)] = name
    for row in rows:
        ref_raw = (row.get("reference") or "").strip()
        if not ref_raw or ref_raw.lower() == "unknown":
            continue
        name = _canonical_reference_name(ref_raw)
        key = _reference_key(name)
        by_key[key] = _prefer_reference_display(by_key.get(key, name), ref_raw)
    return sorted(by_key.values(), key=lambda x: x.lower())


def _coerce_bool(value) -> bool:
    """Accept True/False, 1/0, '1', 'true', 'yes', 'on', 'consultancy'."""
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    if isinstance(value, (int, float)):
        return value != 0
    s = str(value).strip().lower()
    return s in ("1", "true", "yes", "on", "y", "t", "consultancy")


# ── Schema normalisation ────────────────────────────────────────────────────

_ALLOWED_FIELDS = {
    "name", "stage", "technology", "task", "phone", "reference",
    "consultancy", "bgv_certificates", "ctc_percentage",
    "payment", "expected_payment", "follow_up",
    "date", "logged_date", "time", "time_end", "expenses", "notes",
    "telegram_slot", "telegram_user_id",
    "service_type", "interview_scope",
    "slot_confirmed",
    "slots_group_posted",
    "interview_attendee",
    "interview_round",
    "purpose",
}


def minimum_payment_for_slot(row: dict) -> int:
    """Rupee threshold before slot_confirmed is allowed (owner + money rule)."""
    if is_free_service_candidate(row.get("name") or ""):
        return 0
    service_type = _normalise_service_type(row.get("service_type"), row)
    consultancy = bool(row.get("consultancy", False))
    expected = effective_expected_payment(row)
    if service_type == "round_wise":
        return expected
    return min(PROFILE_SERVICE_SLOT_MIN_PAYMENT, expected)


def slot_confirm_block_reason(row: dict) -> str | None:
    """None if slot_confirmed may be set; else human-readable blocker."""
    if not _coerce_bool(row.get("slots_group_posted")):
        return (
            "Confirm the slot screenshot was posted in the Interview slots "
            "WhatsApp group first."
        )
    ref = (row.get("reference") or "").strip()
    if not ref or ref.lower() == "unknown":
        return "Assign an owner (reference) before confirming the interview slot."
    received = int(row.get("payment") or 0)
    need = minimum_payment_for_slot(row)
    if received < need:
        return (
            f"Record at least ₹{need:,} received before confirming the slot "
            f"(currently ₹{received:,})."
        )
    if not (row.get("date") or "").strip():
        return "Set the interview date before confirming the slot."
    return None


def can_confirm_slot(row: dict) -> bool:
    return slot_confirm_block_reason(row) is None


def _normalise_service_type(raw, base: dict | None = None) -> str:
    val = _clean_str(raw if raw is not None else (base or {}).get("service_type", "profile_service")).lower()
    return val if val in VALID_SERVICE_TYPES else "profile_service"


def _normalise_purpose(raw, base: dict | None = None) -> str:
    val = _clean_str(raw if raw is not None else (base or {}).get("purpose", "")).lower().replace(" ", "_")
    if val in VALID_PURPOSES:
        return val
    if "work" in val:
        return "work_support"
    if "experience" in val or "doc" in val:
        return "experience_docs"
    if "interview" in val:
        return "interview_support"
    return "interview_support"


def _normalise_interview_scope(raw, base: dict | None = None) -> str:
    val = _clean_str(
        raw if raw is not None else (base or {}).get("interview_scope", "external"),
    ).lower().replace("-", "_").replace(" ", "_")
    internal_aliases = {
        "non_domestic", "nondomestic", "internal", "international",
        "abroad", "usa", "us", "india_abroad",
    }
    external_aliases = {
        "domestic", "india", "external", "regular", "round",
    }
    if val in internal_aliases:
        return "internal"
    if val in external_aliases:
        return "external"
    return val if val in VALID_INTERVIEW_SCOPES else "external"


def normalise_interview_round(raw) -> str:
    """Canonical interview round label (L1, L2, …) for slot booking."""
    val = _clean_str(raw)
    if not val:
        return ""
    compact = re.sub(r"\s+", "", val).upper()
    if compact in VALID_INTERVIEW_ROUNDS:
        return compact
    m = re.match(r"^L(\d)$", compact, re.IGNORECASE)
    if m:
        label = f"L{m.group(1)}"
        return label if label in VALID_INTERVIEW_ROUNDS else ""
    title = val.title()
    if title in VALID_INTERVIEW_ROUNDS:
        return title
    return ""


def _normalise(record: dict, *, existing: dict | None = None) -> dict:
    """Turn whatever the UI sent into a clean row, preserving existing
    timestamps when patching."""
    base = dict(existing) if existing else {}

    # `consultancy` flips the default baseline: True → ₹15k, False → ₹20k.
    # Stored as a clean bool so the UI doesn't have to guess from strings.
    consultancy = _coerce_bool(record.get("consultancy", base.get("consultancy", False)))
    bgv_certificates = _coerce_bool(record.get("bgv_certificates", base.get("bgv_certificates", False)))
    service_type = _normalise_service_type(record.get("service_type"), base)
    interview_scope = _normalise_interview_scope(record.get("interview_scope"), base)
    if service_type == "round_wise":
        consultancy = False

    default_for_channel = baseline_for_service(
        service_type,
        consultancy=consultancy,
        interview_scope=interview_scope,
        bgv_certificates=bgv_certificates,
    )
    exp_raw = record.get("expected_payment",
                         base.get("expected_payment", default_for_channel))
    expected = _coerce_payment(exp_raw)
    if expected <= 0:
        expected = default_for_channel
    elif (
        service_type == "profile_service"
        and consultancy
        and expected == DEFAULT_EXPECTED_PAYMENT
        and "consultancy" in record
    ):
        expected = CONSULTANCY_EXPECTED_PAYMENT
    elif (
        service_type == "profile_service"
        and not consultancy
        and expected == CONSULTANCY_EXPECTED_PAYMENT
        and "consultancy" in record
    ):
        expected = DEFAULT_EXPECTED_PAYMENT

    # `proofs` is intentionally NOT in _ALLOWED_FIELDS — it's only mutated
    # through add_proof / delete_proof so screenshots can't be wiped by a
    # plain PATCH on the candidate record.
    out = {
        "id":               base.get("id") or _new_id(),
        "name":             canonical_candidate_name(
            _clean_str(record.get("name", base.get("name")))
        ),
        "stage":            _clean_str(record.get("stage", base.get("stage", "in_progress"))).lower().replace(" ", "_"),
        "technology":       canonical_technology(
            _clean_str(record.get("technology", base.get("technology")))
        ),
        "task":             _clean_str(record.get("task", base.get("task", "not_started"))).lower().replace(" ", "_"),
        "phone":            _clean_str(record.get("phone", base.get("phone"))),
        "reference":        _canonical_reference_name(
            _clean_str(record.get("reference", base.get("reference")))
        ),
        "consultancy":      consultancy,
        "bgv_certificates": bgv_certificates,
        "service_type":     service_type,
        "interview_scope":  interview_scope if service_type == "round_wise" else "",
        "payment":          _coerce_payment(record.get("payment", base.get("payment"))),
        "expected_payment": expected,
        "follow_up":        _clean_str(record.get("follow_up", base.get("follow_up"))),
        "purpose":          _normalise_purpose(record.get("purpose"), base),
        "date":             _clean_str(record.get("date", base.get("date"))),
        "logged_date":      _clean_str(record.get("logged_date", base.get("logged_date"))),
        "time":             _clean_str(record.get("time", base.get("time"))),
        "time_end":         _clean_str(record.get("time_end", base.get("time_end"))),
        "expenses":         _clean_str(record.get("expenses", base.get("expenses"))),
        "notes":            sanitize_candidate_notes(_clean_str(record.get("notes", base.get("notes")))),
        "interview_attendee": _canonical_reference_name(
            _clean_str(record.get("interview_attendee", base.get("interview_attendee")))
        ),
        "interview_round":  normalise_interview_round(
            record.get("interview_round", base.get("interview_round", ""))
        ),
        "telegram_slot":    _clean_str(record.get("telegram_slot", base.get("telegram_slot"))),
        "telegram_user_id": int(record.get("telegram_user_id") or base.get("telegram_user_id") or 0) or None,
        "proofs":           list(base.get("proofs") or []),
        "resumes":          list(base.get("resumes") or []),
        "created_at":       base.get("created_at") or _now_iso(),
        "updated_at":       _now_iso(),
    }
    out["slots_group_posted"] = _coerce_bool(
        record.get("slots_group_posted", base.get("slots_group_posted", False))
    )
    want_confirm = _coerce_bool(record.get("slot_confirmed", base.get("slot_confirmed", False)))
    prev_confirm = _coerce_bool(base.get("slot_confirmed", False))
    out["slot_confirmed"] = want_confirm
    if want_confirm and not prev_confirm:
        out["slot_confirmed_at"] = _now_iso()
    elif want_confirm:
        out["slot_confirmed_at"] = base.get("slot_confirmed_at") or _now_iso()
    else:
        out["slot_confirmed"] = False
        out["slot_confirmed_at"] = ""
    out["interview_attendance_status"] = normalise_interview_attendance_status(
        base.get("interview_attendance_status"),
        legacy_attended=_coerce_bool(base.get("interview_attended", False)),
    )
    out["interview_attendance_remark"] = _clean_str(base.get("interview_attendance_remark"))
    out["interview_attended"] = out["interview_attendance_status"] == "attended"
    out["interview_attended_at"] = base.get("interview_attended_at") or ""
    out["interview_attended_by"] = _clean_str(base.get("interview_attended_by"))
    if out["stage"] not in VALID_STAGES:
        out["stage"] = "in_progress"
    if out["task"] not in VALID_TASKS:
        out["task"] = "not_started"
    logged = (out.get("logged_date") or "").strip()[:10]
    day = (out.get("date") or "").strip()[:10]
    if len(logged) != 10 and len(day) == 10 and (not existing or "date" in record):
        out["logged_date"] = day
    return out


def _row_lead_date(row: dict) -> str:
    """When the lead was logged — preserved when interview slots are assigned later."""
    logged = _clean_str(row.get("logged_date"))[:10]
    if len(logged) == 10:
        return logged
    return _clean_str(row.get("date"))[:10]


def _with_computed(row: dict) -> dict:
    """Append derived fields (`balance_due`, `payment_status`) without
    persisting them. Keeps the storage format simple while giving the
    UI a single, server-computed source of truth."""
    consultancy = bool(row.get("consultancy", False))
    service_type = _normalise_service_type(row.get("service_type"), row)
    interview_scope = _normalise_interview_scope(row.get("interview_scope"), row)
    fallback = baseline_for_service(
        service_type,
        consultancy=consultancy,
        interview_scope=interview_scope,
        bgv_certificates=_coerce_bool(row.get("bgv_certificates")),
    )
    expected = effective_expected_payment(row)
    received = int(row.get("payment") or 0)
    balance = max(0, expected - received)
    if received <= 0:
        status = "unpaid"
    elif received >= expected:
        status = "paid"
    else:
        status = "partial"
    enriched = dict(row)
    enriched["consultancy"] = consultancy
    enriched["bgv_certificates"] = _coerce_bool(row.get("bgv_certificates"))
    enriched["service_type"] = service_type
    enriched["interview_scope"] = interview_scope if service_type == "round_wise" else ""
    enriched["expected_payment"] = expected
    enriched["prescribed_baseline"] = fallback
    enriched["balance_due"] = balance
    enriched["payment_status"] = status
    enriched["needs_followup"] = balance > 0
    enriched["handler_commission"] = referrer_commission_amount(row)
    commissionable_expected = max(0, expected - (BGV_CERTIFICATES_PAYMENT if enriched["bgv_certificates"] else 0))
    enriched["handler_commission_max"] = (commissionable_expected * HANDLER_COMMISSION_PCT) // 100
    enriched["company_revenue"] = max(0, received - enriched["handler_commission"])
    proofs = enriched.get("proofs") or []
    # Separate payment proofs from slot screenshots for the Candidates table.
    # Payment VIEW should only show payment screenshots, not interview slot images.
    payment_proofs = [p for p in proofs if not _is_slot_screenshot_proof(p)]
    enriched["proofs"] = payment_proofs
    enriched["proof_count"] = len(payment_proofs)
    # Keep slot screenshots accessible separately (for Daily Ops / interview views)
    enriched["slot_screenshot_proofs"] = [p for p in proofs if _is_slot_screenshot_proof(p)]
    resumes = enriched.get("resumes") or []
    enriched["resumes"] = resumes
    enriched["resume_count"] = len(resumes)
    if resumes:
        enriched["latest_resume"] = max(
            resumes,
            key=lambda r: r.get("uploaded_at") or "",
        )
    else:
        enriched["latest_resume"] = None
    required_details = {
        "name": _clean_str(enriched.get("name")),
        "technology": _clean_str(enriched.get("technology")),
        "date": _clean_str(enriched.get("date")),
        "phone": _clean_str(enriched.get("phone")),
        "reference": _clean_str(enriched.get("reference")),
        "resume": bool(resumes),
        # Once money is recorded, at least one payment proof is required
        # before the row can be considered fully complete.
        "payment_proof": bool(payment_proofs) if received > 0 else True,
    }
    enriched["completion_missing"] = [
        field for field, value in required_details.items() if not value
    ]
    # This is a data-entry completion signal only. An unpaid balance or a
    # future interview slot must not hide it, because those are workflow state.
    enriched["details_complete"] = not enriched["completion_missing"]
    slot_ok = can_confirm_slot(enriched)
    enriched["can_confirm_slot"] = slot_ok
    enriched["slot_confirm_block_reason"] = slot_confirm_block_reason(enriched)
    enriched["slot_confirm_min_payment"] = minimum_payment_for_slot(enriched)
    enriched["interview_attendee_resolved"] = row_interview_attendee(enriched)
    enriched["interview_attendance_status_resolved"] = row_interview_attendance_status(enriched)
    enriched["technology_resolved"] = row_candidate_technology(enriched)
    return enriched


def backfill_tool_default_interview_attendees() -> int:
    """Persist Tool on Keerthana / Satyanarayana slots that still have empty or Bhavana."""
    data = _load(force=True)
    rows = data.get("candidates") or []
    changed = 0
    for i, r in enumerate(rows):
        if not candidate_defaults_to_tool_attendee(r.get("name") or ""):
            continue
        if not _clean_str(r.get("date")):
            continue
        explicit = (r.get("interview_attendee") or "").strip().lower()
        if explicit == "tool":
            continue
        if explicit and explicit not in {"", "bhavana"}:
            continue
        r = dict(r)
        r["interview_attendee"] = "Tool"
        r["updated_at"] = _now_iso()
        rows[i] = r
        changed += 1
    if changed:
        data["candidates"] = rows
        data["updated_at"] = _now_iso()
        _save(data)
        global _load_cache, _load_cache_at
        _load_cache = None
        _load_cache_at = 0.0
    return changed


def backfill_logged_dates() -> int:
    """Set logged_date from earliest slot/lead date (or created_at) per profile client name."""
    data = _load(force=True)
    rows = data.get("candidates") or []
    earliest_by_name: dict[str, str] = {}
    for r in rows:
        if _normalise_service_type(r.get("service_type"), r) == "round_wise":
            continue
        key = _normalise_candidate_name_key(r.get("name") or "")
        if not key:
            continue
        # Use logged_date if available, then date, then created_at
        day = _clean_str(r.get("logged_date"))[:10]
        if len(day) != 10:
            day = _clean_str(r.get("date"))[:10]
        if len(day) != 10:
            day = _clean_str(r.get("created_at"))[:10]
        if len(day) != 10:
            continue
        prev = earliest_by_name.get(key)
        if not prev or day < prev:
            earliest_by_name[key] = day
    changed = 0
    for i, r in enumerate(rows):
        if _normalise_service_type(r.get("service_type"), r) == "round_wise":
            continue
        key = _normalise_candidate_name_key(r.get("name") or "")
        lead = earliest_by_name.get(key, "")
        if len(lead) != 10:
            continue
        current = _clean_str(r.get("logged_date"))[:10]
        if current == lead:
            continue
        r = dict(r)
        r["logged_date"] = lead
        r["updated_at"] = _now_iso()
        rows[i] = r
        changed += 1
    if changed:
        data["candidates"] = rows
        data["updated_at"] = _now_iso()
        _save(data)
        global _load_cache, _load_cache_at
        _load_cache = None
        _load_cache_at = 0.0
    return changed


def backfill_tool_default_candidate_technology() -> int:
    """Persist Data Analyst on Keerthana / Satyanarayana rows still marked Unspecified."""
    data = _load(force=True)
    rows = data.get("candidates") or []
    changed = 0
    for i, r in enumerate(rows):
        if not candidate_defaults_to_tool_attendee(r.get("name") or ""):
            continue
        stored = canonical_technology(r.get("technology") or "")
        if stored not in {"", "Unspecified"}:
            continue
        r = dict(r)
        r["technology"] = TOOL_PROFILE_CANDIDATE_TECHNOLOGY
        r["updated_at"] = _now_iso()
        rows[i] = r
        changed += 1
    if changed:
        data["candidates"] = rows
        data["updated_at"] = _now_iso()
        _save(data)
        global _load_cache, _load_cache_at
        _load_cache = None
        _load_cache_at = 0.0
    return changed


def backfill_canonical_candidate_names() -> int:
    """Merge name variants (PERLA ABHILASH vs Abilash Perla) to one canonical label."""
    data = _load(force=True)
    rows = data.get("candidates") or []
    changed = 0
    for i, r in enumerate(rows):
        old = (r.get("name") or "").strip()
        new = canonical_candidate_name(old)
        if not new or new == old:
            continue
        rows[i] = _normalise({"name": new}, existing=r)
        changed += 1
    if changed:
        data["candidates"] = rows
        data["updated_at"] = _now_iso()
        _save(data)
        global _load_cache, _load_cache_at
        _load_cache = None
        _load_cache_at = 0.0
    return changed


# ── Public API ──────────────────────────────────────────────────────────────

def _apply_list_filters(
    rows: list[dict],
    *,
    stage: str | None = None,
    task: str | None = None,
    search: str | None = None,
    month: str | None = None,
    pending_only: bool = False,
    reference: str | None = None,
    service_type: str | None = None,
) -> list[dict]:
    if stage and stage != "all":
        rows = [r for r in rows if r.get("stage") == stage]
    if task and task != "all":
        rows = [r for r in rows if r.get("task") == task]
    if month and month != "all":
        if month == "undated":
            rows = [r for r in rows if not _row_month(r) and not _row_display_month(r)]
        else:
            rows = [r for r in rows if _row_in_month(r, month)]
    if pending_only:
        rows = [r for r in rows if r.get("balance_due", 0) > 0]
    if reference and reference != "all":
        needle = reference.strip().lower()
        rows = [r for r in rows if (r.get("reference") or "").strip().lower() == needle]
    if service_type and service_type != "all":
        rows = [r for r in rows if _normalise_service_type(r.get("service_type"), r) == service_type]
    if search:
        q = search.strip().lower()
        if q:
            def _hit(r: dict) -> bool:
                if q == "consultancy" and r.get("consultancy"):
                    return True
                for k in ("name", "technology", "reference", "phone", "notes", "follow_up"):
                    if q in (r.get(k) or "").lower():
                        return True
                return False
            rows = [r for r in rows if _hit(r)]
    rows.sort(key=lambda r: (r.get("date") or "", r.get("updated_at") or ""), reverse=True)
    return rows


def _slim_list_row(row: dict) -> dict:
    """Drop payment proof blobs from list payloads — resume metadata stays for the viewer."""
    slim = dict(row)
    slim.pop("proofs", None)
    return slim


def _collapse_profile_candidates(rows: list[dict], *, month: str | None = None) -> list[dict]:
    """Show one Candidates-page record per profile candidate.

    Multiple interview slots are stored as separate rows for scheduling, but
    they are not separate profile candidates.  Keep round-wise support rows
    independent and merge only profile-service rows by normalised name.
    """
    grouped: dict[str, list[dict]] = {}
    result: list[dict] = []
    for row in rows:
        if _normalise_service_type(row.get("service_type"), row) == "round_wise":
            result.append(row)
            continue
        key = " ".join((row.get("name") or "").strip().lower().split())
        if not key:
            result.append(row)
            continue
        grouped.setdefault(key, []).append(row)
    for group in grouped.values():
        # When a month filter is active, prefer the row whose date matches that month.
        # This prevents picking a row with an empty date or wrong month as the winner.
        if month and month != "all":
            month_matching = [r for r in group if _row_display_month(r) == month]
            if month_matching:
                newest = max(month_matching, key=lambda r: (r.get("date") or "", r.get("updated_at") or ""))
            else:
                newest = max(group, key=lambda r: (r.get("updated_at") or "", r.get("date") or ""))
        else:
            newest = max(group, key=lambda r: (r.get("updated_at") or "", r.get("date") or ""))
        merged = dict(newest)
        merged["slot_count"] = len(group)
        # Use the max payment across all slot clones for this profile.
        # Payment is recorded on one slot but the collapsed row should reflect it.
        max_payment = max(int(r.get("payment") or 0) for r in group)
        if max_payment > merged.get("payment", 0):
            merged["payment"] = max_payment
        # A profile may have old interview-slot duplicates.  Keep its explicit
        # Ravinder referral instead of letting a newer duplicate (for example
        # one imported with Thrilok) replace it in the consolidated row.
        ravinder_row = next(
            (r for r in group if _reference_key(r.get("reference") or "") == "ravinder"),
            None,
        )
        if ravinder_row:
            merged["reference"] = "Ravinder"
        elif key in {"keerthana", "satyanarayana", "adivi satyanarayana"}:
            merged["reference"] = "Ravinder"
        all_resumes = {item.get("id"): item for r in group for item in (r.get("resumes") or []) if item.get("id")}
        if all_resumes:
            merged["resumes"] = list(all_resumes.values())
            merged["resume_count"] = len(all_resumes)
            merged["latest_resume"] = max(all_resumes.values(), key=lambda item: item.get("uploaded_at") or "")
        # Merge proofs from all slot clones so they're visible regardless of which row wins
        # Deduplicate by proof ID to avoid showing the same proof multiple times
        # Exclude slot screenshots (they should appear separately, not in payment proofs)
        all_proofs = {}
        slot_proofs = {}
        for r in group:
            slot_ss_id = r.get("slot_screenshot_proof_id")
            for item in (r.get("proofs") or []):
                pid = item.get("id")
                if not pid or pid in all_proofs or pid in slot_proofs:
                    continue
                # Identify slot screenshots by their note or by matching the slot_screenshot_proof_id
                is_slot_ss = (
                    pid == slot_ss_id
                    or (item.get("note") or "").lower().startswith("interview slot screenshot")
                )
                if is_slot_ss:
                    slot_proofs[pid] = item
                else:
                    all_proofs[pid] = item
        if all_proofs:
            merged["proofs"] = list(all_proofs.values())
            merged["proof_count"] = len(all_proofs)
        if slot_proofs:
            merged["slot_screenshot_proofs"] = list(slot_proofs.values())
        result.append(merged)
    result.sort(key=lambda r: (r.get("date") or "", r.get("updated_at") or ""), reverse=True)
    return result


def _in_progress_rows(rows: list[dict], month: str | None) -> list[dict]:
    out = [r for r in rows if r.get("stage") == "in_progress"]
    if month and month != "all":
        if month == "undated":
            out = [r for r in out if not _row_month(r)]
        else:
            out = [r for r in out if _row_in_month(r, month)]
    return out


def _attach_pending_work_stats(payload: dict, pw: dict) -> dict:
    payload["pending_works"] = pw["works"]
    payload["pending_works_count"] = pw["count"]
    payload["pending_works_candidates"] = pw["candidate_count"]
    payload["pending_works_checked"] = pw["candidates_checked"]
    payload["pending_works_by_kind"] = pw["by_kind"]
    return payload


def list_candidates(*, stage: str | None = None, task: str | None = None,
                    search: str | None = None, month: str | None = None,
                    pending_only: bool = False,
                    reference: str | None = None,
                    service_type: str | None = None) -> list[dict]:
    """Return candidates sorted by most-recent first.
    Optional filters: by stage, by task, by free-text search across
    name / technology / reference / phone / notes / follow_up, by month
    ('YYYY-MM'), `pending_only=True` to keep only rows where the
    received payment is less than the expected baseline, and `reference`
    for an exact case-insensitive handler match (so the dashboard can
    show only one handler's leads)."""
    reconcile_resume_metadata()
    data = _load()
    rows = [_with_computed(r) for r in (data.get("candidates") or [])]
    # Apply month filter BEFORE collapse so we don't accidentally pick
    # a June slot when filtering for July (collapse picks newest by updated_at).
    if month and month != "all":
        if month == "undated":
            rows = [r for r in rows if not _row_month(r) and not _row_display_month(r)]
        else:
            rows = [r for r in rows if _row_in_month(r, month)]
    # Consolidate after month filtering. Reference filter still needs to happen
    # after collapse to respect the Ravinder fallback logic.
    rows = _collapse_profile_candidates(rows, month=month)
    return _apply_list_filters(
        rows,
        stage=stage,
        task=task,
        search=search,
        month=None,  # Already applied above
        pending_only=pending_only,
        reference=reference,
        service_type=service_type,
    )


def _is_roster_placeholder(row: dict) -> bool:
    """Skip empty import stubs from the active tech roster (e.g. Unspecified / not started)."""
    tech = (row.get("technology") or "").strip().lower()
    task = (row.get("task") or "").strip().lower()
    phone = (row.get("phone") or "").strip()
    if tech not in {"", "unspecified"}:
        return False
    if task != "not_started":
        return False
    return not phone


def _hidden_from_candidates_page(name: str) -> bool:
    """Match dashboard Candidates page — hide Tool-only roster names."""
    return is_free_service_candidate(name)


PENDING_WORK_LABELS = {
    "missing_reference": "Assign referrer",
    "missing_resume": "Upload resume",
    "payment_due": "Payment pending",
    "missing_follow_up": "Add follow-up remark",
    "missing_phone": "Add phone number",
}

PENDING_WORK_PRIORITY = {
    "missing_reference": 10,
    "missing_resume": 20,
    "payment_due": 30,
    "missing_follow_up": 35,
    "missing_phone": 50,
}


def _pending_work_item(*, kind: str, row: dict, detail: str = "") -> dict:
    return {
        "id": f"{kind}:{row.get('id')}",
        "kind": kind,
        "label": PENDING_WORK_LABELS[kind],
        "detail": detail,
        "priority": PENDING_WORK_PRIORITY[kind],
        "candidate_id": row.get("id"),
        "candidate_name": row.get("name") or "",
        "reference": row.get("reference") or "",
        "technology": row.get("technology") or "",
        "service_type": row.get("service_type") or "profile_service",
    }


def _merge_profile_rows_for_pending(rows: list[dict]) -> dict:
    """Collapse profile slot clones — same rules as the Candidates table merge."""
    rep = max(
        rows,
        key=lambda r: (
            int(r.get("payment") or 0),
            len(r.get("resumes") or []),
            len(r.get("proofs") or []),
            (r.get("date") or ""),
        ),
    )
    payment = max(int(r.get("payment") or 0) for r in rows)
    # Match dashboard merge: use representative row's channel-aware expected, not max across clones.
    expected = effective_expected_payment(rep)
    resume_count = max(len(r.get("resumes") or []) for r in rows)
    phone = next((r.get("phone") for r in rows if _clean_str(r.get("phone"))), "")
    reference = next(
        (
            r.get("reference")
            for r in rows
            if _clean_str(r.get("reference"))
            and (r.get("reference") or "").strip().lower() != "unknown"
        ),
        rep.get("reference"),
    )
    follow_up = next((r.get("follow_up") for r in rows if _clean_str(r.get("follow_up"))), "")
    merged = {
        **rep,
        "payment": payment,
        "expected_payment": expected,
        "balance_due": max(0, expected - payment),
        "resume_count": resume_count,
        "phone": phone or rep.get("phone"),
        "reference": reference or rep.get("reference"),
        "follow_up": follow_up or rep.get("follow_up"),
    }
    return merged


_STAGE_RANK = {"completed": 4, "in_progress": 3, "fail": 2, "dropped": 1}


def _merge_profile_rows_for_stats(rows: list[dict]) -> dict:
    """Collapse slot clones for KPI aggregates — max payment once per profile."""
    merged = _merge_profile_rows_for_pending(rows)
    merged["stage"] = max(
        (r.get("stage") or "in_progress" for r in rows),
        key=lambda s: _STAGE_RANK.get(s, 0),
    )
    merged["consultancy"] = any(_coerce_bool(r.get("consultancy")) for r in rows)
    return merged


def _stats_rows_deduped(rows: list[dict]) -> list[dict]:
    """One logical client per profile name; round-wise stays one row per slot."""
    profile_by_name: dict[str, list[dict]] = {}
    round_rows: list[dict] = []
    for row in rows:
        if _hidden_from_candidates_page(row.get("name") or ""):
            continue
        if _is_roster_placeholder(row):
            continue
        if _normalise_service_type(row.get("service_type"), row) == "round_wise":
            round_rows.append(row)
            continue
        key = _normalise_candidate_name_key(row.get("name") or "")
        if not key:
            continue
        profile_by_name.setdefault(key, []).append(row)
    merged_profiles = [
        _merge_profile_rows_for_stats(group)
        for group in profile_by_name.values()
    ]
    return merged_profiles + round_rows


def _pending_collections_from_rows(
    rows: list[dict],
) -> tuple[int, int, int, dict[str, dict[str, int]]]:
    """Pending balance once per profile client — not per slot clone."""
    profile_by_name: dict[str, list[dict]] = {}
    round_rows: list[dict] = []
    for row in rows:
        if _normalise_service_type(row.get("service_type"), row) == "round_wise":
            round_rows.append(row)
            continue
        key = _normalise_candidate_name_key(row.get("name") or "")
        if not key:
            continue
        profile_by_name.setdefault(key, []).append(row)

    merged = [
        _merge_profile_rows_for_pending(group)
        for group in profile_by_name.values()
    ] + round_rows

    pending_total = 0
    pending_count = 0
    pending_no_remark = 0
    by_ref: dict[str, dict[str, int]] = {}

    for row in merged:
        balance = int(row.get("balance_due") or 0)
        if balance <= 0:
            expected = effective_expected_payment(row)
            paid = int(row.get("payment") or 0)
            balance = max(0, expected - paid)
        if balance <= 0:
            continue
        pending_total += balance
        pending_count += 1
        if not (row.get("follow_up") or "").strip():
            pending_no_remark += 1
        ref_key = _reference_key(row.get("reference") or "Unknown")
        bucket = by_ref.setdefault(ref_key, {"pending_total": 0, "pending_count": 0})
        bucket["pending_total"] += balance
        bucket["pending_count"] += 1

    return pending_total, pending_count, pending_no_remark, by_ref


def _collect_pending_works_for_row(row: dict) -> list[dict]:
    works: list[dict] = []
    ref = (row.get("reference") or "").strip()
    if not ref or ref.lower() == "unknown":
        works.append(_pending_work_item(kind="missing_reference", row=row))
    if int(row.get("resume_count") or len(row.get("resumes") or [])) == 0:
        works.append(_pending_work_item(kind="missing_resume", row=row))
    # Payment balance is enforced at slot booking — do not surface as pending work.
    if not (row.get("phone") or "").strip():
        works.append(_pending_work_item(kind="missing_phone", row=row))
    return works


def _pending_works_core(rows: list[dict]) -> dict:
    """Build pending-work items from pre-filtered in-progress rows."""
    rows = [
        r for r in rows
        if not _hidden_from_candidates_page(r.get("name") or "")
        and not _is_roster_placeholder(r)
    ]
    profile_groups: dict[str, list[dict]] = {}
    round_rows: list[dict] = []
    for row in rows:
        if _normalise_service_type(row.get("service_type"), row) == "round_wise":
            round_rows.append(row)
            continue
        key = _normalise_candidate_name_key(row.get("name") or "")
        if not key:
            continue
        profile_groups.setdefault(key, []).append(row)

    merged_profiles = [
        _merge_profile_rows_for_pending(group)
        for group in profile_groups.values()
    ]
    works: list[dict] = []
    for row in merged_profiles + round_rows:
        works.extend(_collect_pending_works_for_row(row))
    works.sort(
        key=lambda item: (
            item["priority"],
            (item.get("candidate_name") or "").lower(),
        ),
    )
    by_kind: dict[str, int] = {}
    candidate_keys: set[str] = set()
    for item in works:
        by_kind[item["kind"]] = by_kind.get(item["kind"], 0) + 1
        candidate_keys.add(_normalise_candidate_name_key(item.get("candidate_name") or ""))
    return {
        "works": works,
        "count": len(works),
        "candidate_count": len(candidate_keys),
        "candidates_checked": len(merged_profiles) + len(round_rows),
        "by_kind": by_kind,
    }


def pending_works(*, month: str | None = None, reference: str | None = None) -> dict:
    """Auto-detected operator to-dos for active in-progress candidates.

    Omit `month` or pass ``all`` to scan the whole active pipeline (default for
    dashboard alerts). Pass ``YYYY-MM`` only when a month-scoped view is needed.
    """
    month_filter = month if month and month != "all" else None
    rows = list_candidates(stage="in_progress", month=month_filter, reference=reference)
    return _pending_works_core(rows)


def active_roster(
    *,
    month: str | None = None,
    reference: str | None = None,
) -> dict:
    """Active (in_progress) candidates grouped by technology for roster views."""
    rows = [
        r for r in list_candidates(stage="in_progress", month=month, reference=reference)
        if not _is_roster_placeholder(r)
    ]
    by_technology: dict[str, list[dict]] = {}
    for row in rows:
        tech = canonical_technology(row.get("technology") or "")
        by_technology.setdefault(tech, []).append(row)
    tech_counts = {tech: len(items) for tech, items in by_technology.items()}
    sorted_techs = sorted(
        by_technology.keys(),
        key=lambda t: (-len(by_technology[t]), t.lower()),
    )
    return {
        "candidates": rows,
        "count": len(rows),
        "by_technology": tech_counts,
        "groups": {tech: by_technology[tech] for tech in sorted_techs},
    }


_SLOT_SCREENSHOT_NOTE_RE = re.compile(
    r"slot\s*screenshot|interview\s*(slot\s*)?screenshot|interview\s*confirmation",
    re.I,
)


def _is_slot_screenshot_proof(proof: dict) -> bool:
    note = (proof.get("note") or "").strip()
    if note and _SLOT_SCREENSHOT_NOTE_RE.search(note):
        return True
    if "payment" in note.lower():
        return False
    oname = (proof.get("original_name") or proof.get("filename") or "").lower()
    return oname.startswith("slot-screenshot")


def _slim_slot_screenshot_proof(cid: str, proof: dict) -> dict:
    pid = proof.get("id")
    return {
        "id": pid,
        "candidate_id": cid,
        "url": f"/candidates/{cid}/proofs/{pid}",
        "note": proof.get("note"),
        "uploaded_at": proof.get("uploaded_at"),
        "original_name": proof.get("original_name") or proof.get("filename"),
    }


def _latest_slot_screenshot_proof(row: dict) -> dict | None:
    cid = str(row.get("id") or "")
    proof_id = _clean_str(row.get("slot_screenshot_proof_id"))
    if cid and proof_id:
        hit = get_proof(cid, proof_id)
        if hit:
            _, entry = hit
            if _is_slot_screenshot_proof(entry):
                return _slim_slot_screenshot_proof(cid, entry)
    proofs = row.get("proofs") or []
    hits = [p for p in proofs if _is_slot_screenshot_proof(p)]
    if len(hits) == 1:
        return _slim_slot_screenshot_proof(cid, hits[0])
    return None


def _resolve_slot_screenshot_proof(
    row: dict,
    *,
    by_id: dict[str, dict],
    by_name: dict[str, list[dict]],
) -> dict | None:
    """Return the slot screenshot stored on this interview row only."""
    del by_name  # kept for call-site compatibility
    cid = str(row.get("id") or "")
    full = by_id.get(cid) or row
    return _latest_slot_screenshot_proof(full)


def _enrich_interview_rows_with_slot_screenshots(rows: list[dict]) -> list[dict]:
    """Attach slot_screenshot_proof from this row or a same-name profile/slot clone."""
    if not rows:
        return rows
    all_candidates = _load().get("candidates") or []
    by_id = {str(raw.get("id") or ""): raw for raw in all_candidates if raw.get("id")}
    by_name: dict[str, list[dict]] = {}
    for raw in all_candidates:
        key = _normalise_candidate_name_key(
            canonical_candidate_name((raw.get("name") or "").strip()),
        )
        if key:
            by_name.setdefault(key, []).append(raw)
    enriched: list[dict] = []
    for row in rows:
        r = dict(row)
        proof = _resolve_slot_screenshot_proof(r, by_id=by_id, by_name=by_name)
        if proof:
            r["slot_screenshot_proof"] = proof
        enriched.append(r)
    return enriched


def daily_interview_roster(
    day: str,
    *,
    viewer_reference: str | None = None,
    filter_attendee: str | None = None,
    filter_search: str | None = None,
    filter_channel: str | None = None,
    filter_round: str | None = None,
    filter_technology: str | None = None,
    include_unconfirmed: bool = False,
) -> dict:
    """Confirmed interview slots for one calendar day (YYYY-MM-DD).

    Interview attenders (Nikhila, Bhavana) see slots assigned to them.
    Other handlers see only their referred candidates. Admins see everything.
    """
    day = (day or "").strip()[:10]
    if len(day) != 10 or day[4] != "-" or day[7] != "-":
        raise ValueError("date must be YYYY-MM-DD")

    rows = _interview_rows_for_range(day, day, include_unconfirmed=include_unconfirmed)
    rows = _filter_interview_rows(
        rows,
        viewer_reference=viewer_reference,
        filter_attendee=filter_attendee,
        filter_search=filter_search,
        filter_channel=filter_channel,
        filter_round=filter_round,
        filter_technology=filter_technology,
    )
    counts = _interview_attendance_counts(rows)
    rows = _enrich_interview_rows_with_slot_screenshots(rows)
    return {
        "date": day,
        "interviews": rows,
        "count": len(rows),
        **counts,
    }


def _interview_rows_for_range(
    from_date: str,
    to_date: str,
    *,
    include_unconfirmed: bool = False,
) -> list[dict]:
    start = (from_date or "").strip()[:10]
    end = (to_date or "").strip()[:10]
    if len(start) != 10 or len(end) != 10:
        raise ValueError("from and to must be YYYY-MM-DD")
    if start > end:
        start, end = end, start
    rows: list[dict] = []
    for raw in _load().get("candidates") or []:
        if raw.get("stage") in {"dropped", "fail"}:
            continue
        slot_date = (raw.get("date") or "").strip()[:10]
        if not slot_date or slot_date < start or slot_date > end:
            continue
        if not include_unconfirmed and not _coerce_bool(raw.get("slot_confirmed")):
            continue
        rows.append(_with_computed(raw))
    return rows


def _interview_time_sort_key(value: str) -> tuple[int, str]:
    """Minutes since midnight — earliest interview first in roster lists."""
    raw = (value or "").strip()
    if not raw:
        return (24 * 60 + 1, "")
    s = re.sub(r"\s+", " ", raw.lower().replace(".", ":"))
    s = s.replace("a.m.", "am").replace("p.m.", "pm")

    m = re.match(r"^(\d{1,2}):(\d{2})(?::\d{2})?(?:\s*(am|pm))?$", s)
    if m:
        hour = int(m.group(1))
        minute = int(m.group(2))
        ampm = m.group(3)
        if ampm == "pm" and hour < 12:
            hour += 12
        elif ampm == "am" and hour == 12:
            hour = 0
        if 0 <= hour <= 23 and 0 <= minute <= 59:
            return (hour * 60 + minute, raw)

    m = re.match(r"^(\d{1,2})(?::(\d{2}))?\s*(am|pm)$", s)
    if m:
        hour = int(m.group(1))
        minute = int(m.group(2) or 0)
        if m.group(3) == "pm" and hour < 12:
            hour += 12
        elif m.group(3) == "am" and hour == 12:
            hour = 0
        if 0 <= hour <= 23 and 0 <= minute <= 59:
            return (hour * 60 + minute, raw)

    return (24 * 60, raw)


def _normalize_iso_date(value: str) -> str:
    """YYYY-MM-DD with zero-padded month/day so string sort matches calendar order."""
    raw = _clean_str(value)[:10]
    if not raw:
        return ""
    m = re.match(r"^(\d{4})-(\d{1,2})-(\d{1,2})$", raw)
    if not m:
        return raw
    y, mo, d = int(m.group(1)), int(m.group(2)), int(m.group(3))
    return f"{y:04d}-{mo:02d}-{d:02d}"


def _slot_chronological_sort_key(row: dict) -> tuple:
    """Earliest interview first — date, then time of day, then name."""
    day = _normalize_iso_date(row.get("date") or "")
    time_mins = _interview_time_sort_key(row.get("time") or "")[0]
    return (day, time_mins, (row.get("name") or "").lower())


def _slot_range_minutes(time: str, time_end: str = "") -> tuple[int, int] | None:
    """Start/end minutes since midnight; default 1hr when end missing or invalid."""
    start = _interview_time_sort_key(time or "")[0]
    if start >= 24 * 60:
        return None
    end = _interview_time_sort_key(time_end or "")[0]
    if end >= 24 * 60 or not (time_end or "").strip() or end <= start:
        end = start + 60
    return start, end


def _slot_ranges_overlap(a: tuple[int, int], b: tuple[int, int]) -> bool:
    return a[0] < b[1] and b[0] < a[1]


def _interview_slot_still_upcoming(
    date_str: str,
    time: str,
    time_end: str = "",
    *,
    now: float | None = None,
) -> bool:
    """True when the slot end (IST) is still in the future — hides completed interviews."""
    from core.ist_time import ist_now

    day = (date_str or "").strip()[:10]
    if len(day) != 10:
        return True
    rng = _slot_range_minutes(time, time_end)
    if not rng:
        return True
    end_min = rng[1]
    try:
        y, m, d = int(day[:4]), int(day[5:7]), int(day[8:10])
    except ValueError:
        return True
    now_dt = ist_now(now)
    slot_end = now_dt.replace(
        year=y, month=m, day=d,
        hour=end_min // 60, minute=end_min % 60,
        second=0, microsecond=0,
    )
    return now_dt < slot_end


def _filter_upcoming_only_rows(rows: list[dict]) -> list[dict]:
    """Daily ops Upcoming tab — pending slots only (exclude resolved attendance)."""
    out: list[dict] = []
    for row in rows:
        status = row_interview_attendance_status(row)
        if status in ("attended", "not_attended", "cancelled", "rescheduled"):
            continue
        out.append(row)
    out.sort(key=_slot_chronological_sort_key)
    return out


def _split_pending_interviews_by_slot_phase(rows: list[dict]) -> tuple[list[dict], list[dict]]:
    """Pending rows split into scheduled (slot not ended) vs awaiting status update."""
    scheduled: list[dict] = []
    awaiting: list[dict] = []
    for raw in rows:
        if row_interview_attendance_status(raw):
            continue
        row = dict(raw)
        slot_date = (row.get("date") or "").strip()[:10]
        slot_time = (row.get("time") or "").strip()
        slot_end = (row.get("time_end") or "").strip()
        still = _interview_slot_still_upcoming(slot_date, slot_time, slot_end)
        row["slot_phase"] = "scheduled" if still else "awaiting_status"
        if still:
            scheduled.append(row)
        else:
            awaiting.append(row)
    scheduled.sort(key=_slot_chronological_sort_key)
    awaiting.sort(key=_slot_chronological_sort_key)
    return scheduled, awaiting


def find_interview_slot_conflicts(
    date: str,
    time: str,
    time_end: str = "",
    *,
    exclude_candidate_id: str | None = None,
) -> list[dict]:
    """Confirmed slots on the same day that overlap the proposed time range."""
    day = _clean_str(date)[:10]
    if len(day) != 10:
        return []
    proposed = _slot_range_minutes(time, time_end)
    if not proposed:
        return []
    exclude = _clean_str(exclude_candidate_id or "")
    conflicts: list[dict] = []
    for raw in _load().get("candidates") or []:
        if raw.get("stage") in {"dropped", "fail"}:
            continue
        if not _coerce_bool(raw.get("slot_confirmed")):
            continue
        cid = _clean_str(raw.get("id") or "")
        if exclude and cid == exclude:
            continue
        slot_date = _clean_str(raw.get("date") or "")[:10]
        if slot_date != day:
            continue
        existing = _slot_range_minutes(raw.get("time") or "", raw.get("time_end") or "")
        if not existing or not _slot_ranges_overlap(proposed, existing):
            continue
        row = _with_computed(raw)
        conflicts.append({
            "id": cid,
            "name": row.get("name") or "",
            "date": slot_date,
            "time": row.get("time") or "",
            "time_end": row.get("time_end") or "",
            "interview_attendee": row_interview_attendee(row),
        })
    conflicts.sort(
        key=lambda r: (
            _interview_time_sort_key(r.get("time") or "")[0],
            (r.get("name") or "").lower(),
        ),
    )
    return conflicts


class SlotBookedError(ValueError):
    """Raised when a new slot overlaps an existing confirmed interview."""

    def __init__(
        self,
        *,
        date: str,
        time: str,
        time_end: str,
        conflicts: list[dict],
    ):
        self.date = date
        self.time = time
        self.time_end = time_end
        self.conflicts = conflicts
        if len(conflicts) == 1:
            who = conflicts[0].get("name") or "another candidate"
            super().__init__(f"This interview slot is already booked — {who} has this time.")
        else:
            names = ", ".join(c.get("name") or "Unknown" for c in conflicts[:3])
            if len(conflicts) > 3:
                names = f"{names} (+{len(conflicts) - 3} more)"
            super().__init__(f"This interview slot is already booked — overlaps with {names}.")


class PaymentDueError(ValueError):
    """Raised when a candidate with dues must upload payment proof before booking."""

    def __init__(self, *, name: str, balance_due: int, needs_proof: bool = True):
        self.name = name
        self.balance_due = balance_due
        self.needs_proof = needs_proof
        if needs_proof:
            msg = (
                f"₹{balance_due:,} payment is pending for {name}. "
                "Upload your payment screenshot first, then book the interview slot."
            )
        else:
            msg = (
                f"₹{balance_due:,} payment is pending for {name}. "
                "Please pay your handler before booking an interview slot."
            )
        super().__init__(msg)


PAYMENT_PROOF_MAX_AGE_HOURS = 12


def _proof_uploaded_recently(entry: dict, max_hours: int = PAYMENT_PROOF_MAX_AGE_HOURS) -> bool:
    raw = (entry.get("uploaded_at") or "").strip()
    if not raw:
        return False
    try:
        ts = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)
        return datetime.now(timezone.utc) - ts <= timedelta(hours=max_hours)
    except ValueError:
        return False


def _best_row_for_slot_name(name: str) -> dict | None:
    """Representative in-progress profile row for public slot / proof actions."""
    canon = canonical_candidate_name(_clean_str(name))
    key = _normalise_candidate_name_key(canon)
    if not key:
        return None
    rows = [
        r for r in list_candidates(stage="in_progress", month="all")
        if _normalise_service_type(r.get("service_type"), r) != "round_wise"
    ]
    best: dict | None = None
    for row in rows:
        if _normalise_candidate_name_key(row.get("name") or "") != key:
            continue
        if best is None or _slot_picker_row_score(row, prefer_react_js=True) > _slot_picker_row_score(
            best, prefer_react_js=True
        ):
            best = row
    if best:
        return best
    for row in list_candidates(stage="in_progress", month="all"):
        if _normalise_candidate_name_key(row.get("name") or "") == key:
            return row
    return None


def candidate_id_for_slot_name(name: str) -> str | None:
    row = _best_row_for_slot_name(name)
    cid = (row or {}).get("id")
    return str(cid) if cid else None


def merged_balance_due_for_name(name: str, rows: list[dict] | None = None) -> int:
    """Outstanding balance once per profile — merged slot clones."""
    canon = canonical_candidate_name(_clean_str(name))
    if not canon or is_free_service_candidate(canon):
        return 0
    key = _normalise_candidate_name_key(canon)
    if not key:
        return 0
    if rows is None:
        rows = [_with_computed(r) for r in list_candidates(stage="in_progress", month="all")]
    else:
        rows = [_with_computed(r) for r in rows]
    profile_rows = [
        r for r in rows
        if _normalise_candidate_name_key(r.get("name") or "") == key
        and _normalise_service_type(r.get("service_type"), r) != "round_wise"
    ]
    if not profile_rows:
        profile_rows = [
            r for r in rows
            if _normalise_candidate_name_key(r.get("name") or "") == key
        ]
    if not profile_rows:
        return 0
    if len(profile_rows) == 1 and _normalise_service_type(profile_rows[0].get("service_type"), profile_rows[0]) == "round_wise":
        rep = profile_rows[0]
    else:
        rep = _merge_profile_rows_for_pending(profile_rows)
    balance = int(rep.get("balance_due") or 0)
    if balance <= 0:
        expected = effective_expected_payment(rep)
        paid = int(rep.get("payment") or 0)
        balance = max(0, expected - paid)
    return balance


def slot_booking_payment_block_reason(
    name: str,
    *,
    payment_proof_id: str | None = None,
) -> str | None:
    """None if the candidate may book; else human-readable payment blocker."""
    due = merged_balance_due_for_name(name)
    if due <= 0:
        return None
    canon = canonical_candidate_name(_clean_str(name))
    # If candidate already has payment proofs on file, allow booking
    cid = candidate_id_for_slot_name(name)
    if cid:
        data = _load()
        for row in data.get("candidates") or []:
            if row.get("id") == cid:
                if row.get("proofs") and len(row.get("proofs", [])) > 0:
                    return None  # Has proofs on file — allow
                break
    if not payment_proof_id:
        return (
            f"₹{due:,} payment is pending for {canon or name}. "
            "Upload your payment screenshot first, then book the interview slot."
        )
    if not cid:
        return "Candidate not found — contact your coordinator."
    hit = get_proof(cid, payment_proof_id.strip())
    if not hit:
        return "Payment screenshot not found — upload it again before booking."
    _path, entry = hit
    if not _proof_uploaded_recently(entry):
        return (
            "Your payment screenshot has expired — upload a fresh payment screenshot, "
            "then book the interview slot."
        )
    return None


def public_add_payment_proof_for_name(
    name: str,
    *,
    data: bytes,
    original_name: str,
    mime_type: str,
    note: str = "",
) -> dict:
    """Attach a payment screenshot from the public submit-slot page.
    
    Also auto-updates the received payment amount based on OCR detection.
    """
    canon = canonical_candidate_name(_clean_str(name))
    if not canon:
        raise ValueError("Enter your name")
    due = merged_balance_due_for_name(canon)
    if due <= 0:
        raise ValueError("No payment due — you can book your interview slot directly.")
    cid = candidate_id_for_slot_name(canon)
    if not cid:
        raise ValueError("Candidate not found — contact your coordinator.")
    caption = _clean_str(note)[:200]
    if not caption:
        caption = f"Payment proof · ₹{due:,} due · submit-slot"
    entry = add_proof(
        cid,
        data=data,
        original_name=original_name,
        mime_type=mime_type,
        note=caption,
    )
    if entry is None:
        raise ValueError("Could not save payment screenshot — try again")
    # Auto-update received amount: add the due amount to payment
    # (since validation already confirmed the proof covers the full due)
    try:
        _auto_increment_payment_on_proof(cid, due)
    except Exception:
        pass  # Don't fail the upload if auto-update fails
    new_due = merged_balance_due_for_name(canon)
    return {
        "candidate_id": cid,
        "proof_id": entry["id"],
        "proof": entry,
        "balance_due": new_due,
        "name": canon,
    }


def _auto_increment_payment_on_proof(cid: str, amount_proven: int) -> None:
    """Add the proven amount to the candidate's received payment field."""
    data = _load(force=True)
    rows = data.get("candidates") or []
    for i, row in enumerate(rows):
        if row.get("id") == cid:
            current_payment = int(row.get("payment") or 0)
            expected = effective_expected_payment(row)
            new_payment = min(current_payment + amount_proven, expected)
            if new_payment > current_payment:
                rows[i] = dict(row)
                rows[i]["payment"] = new_payment
                rows[i]["updated_at"] = _now_iso()
                data["candidates"] = rows
                _save(data)
            return

def _resolve_public_slot_conflicts(
    *,
    candidate_name: str,
    date: str,
    time: str,
    time_end: str,
    exclude_candidate_id: str | None = None,
) -> None:
    """Apply booking priority: low-priority names yield slots to everyone else."""
    conflicts = find_interview_slot_conflicts(
        date, time, time_end, exclude_candidate_id=exclude_candidate_id,
    )
    if not conflicts:
        return

    if is_low_priority_slot_booker(candidate_name):
        raise SlotBookedError(
            date=date,
            time=time,
            time_end=time_end,
            conflicts=conflicts,
        )

    blocking = [
        c for c in conflicts
        if not is_low_priority_slot_booker(c.get("name") or "")
    ]
    bumpable = [
        c for c in conflicts
        if is_low_priority_slot_booker(c.get("name") or "")
    ]

    if blocking:
        raise SlotBookedError(
            date=date,
            time=time,
            time_end=time_end,
            conflicts=blocking,
        )

    for row in bumpable:
        cancel_interview_slot(candidate_id=row["id"])


def _filter_interview_rows(
    rows: list[dict],
    *,
    viewer_reference: str | None = None,
    filter_attendee: str | None = None,
    filter_search: str | None = None,
    filter_channel: str | None = None,
    filter_round: str | None = None,
    filter_technology: str | None = None,
) -> list[dict]:
    attendee_filter = (filter_attendee or "").strip()
    search_filter = (filter_search or "").strip()
    channel_filter = (filter_channel or "").strip().lower()
    viewer = (viewer_reference or "").strip()
    # Daily Ops is a shared operations roster.  Do not hide another
    # handler's booked interview from a handler session; every authenticated
    # operator needs the same live schedule as admin.
    if attendee_filter:
        needle = attendee_filter.lower()
        rows = [
            r for r in rows
            if _reference_key(row_interview_attendee(r)) == needle
        ]
    if search_filter:
        rows = [
            r for r in rows
            if candidate_matches_search(r.get("name") or "", search_filter)
        ]
    if channel_filter and channel_filter != "all":
        if channel_filter == "round_wise":
            rows = [
                r for r in rows
                if _normalise_service_type(r.get("service_type"), r) == "round_wise"
            ]
        elif channel_filter in {"profile", "profile_service"}:
            rows = [
                r for r in rows
                if _normalise_service_type(r.get("service_type"), r) != "round_wise"
            ]

    # Round filter — normalize both the filter value and each row's round
    round_val = (filter_round or "").strip()
    if round_val:
        round_key = normalise_interview_round(round_val)
        rows = [
            r for r in rows
            if normalise_interview_round(r.get("interview_round")) == round_key
        ]

    # Technology filter — normalize and compare case-insensitively
    tech_val = (filter_technology or "").strip()
    if tech_val:
        tech_key = canonical_technology(tech_val).lower()
        rows = [
            r for r in rows
            if canonical_technology(r.get("technology") or "").lower() == tech_key
        ]

    rows.sort(key=_slot_chronological_sort_key)
    return rows


def _interview_slot_is_future(row: dict) -> bool:
    from datetime import date

    slot_date = (row.get("date") or "").strip()[:10]
    if len(slot_date) != 10:
        return False
    return slot_date > date.today().isoformat()


def interview_monitor(
    from_date: str,
    to_date: str,
    *,
    viewer_reference: str | None = None,
    filter_attendee: str | None = None,
    filter_search: str | None = None,
    filter_channel: str | None = None,
    filter_round: str | None = None,
    filter_technology: str | None = None,
    include_unconfirmed: bool = False,
    upcoming_only: bool = False,
) -> dict:
    """All confirmed interview slots in a date range — admin monitor view."""
    rows = _interview_rows_for_range(
        from_date,
        to_date,
        include_unconfirmed=include_unconfirmed,
    )
    rows = _filter_interview_rows(
        rows,
        viewer_reference=viewer_reference,
        filter_attendee=filter_attendee,
        filter_search=filter_search,
        filter_channel=filter_channel,
        filter_round=filter_round,
        filter_technology=filter_technology,
    )
    counts = _interview_attendance_counts(rows)
    if upcoming_only:
        rows = _filter_upcoming_only_rows(rows)
    rows = _enrich_interview_rows_with_slot_screenshots(rows)
    by_date: dict[str, list[dict]] = {}
    by_attendee: dict[str, int] = {}
    for row in rows:
        day = (row.get("date") or "")[:10]
        by_date.setdefault(day, []).append(row)
        att = row_interview_attendee(row)
        by_attendee[att] = by_attendee.get(att, 0) + 1
    start = (from_date or "").strip()[:10]
    end = (to_date or "").strip()[:10]
    if start > end:
        start, end = end, start
    return {
        "from": start,
        "to": end,
        "interviews": rows,
        "count": len(rows),
        **counts,
        "by_date": {day: by_date[day] for day in sorted(by_date.keys())},
        "by_attendee": dict(sorted(by_attendee.items(), key=lambda kv: kv[0].lower())),
    }


def interview_upcoming(
    *,
    days: int = 14,
    filter_search: str | None = None,
    filter_attendee: str | None = None,
    filter_channel: str | None = None,
    viewer_reference: str | None = None,
    include_today_pending: bool = True,
    phase: str | None = None,
    lookback_days: int = 30,
) -> dict:
    """Team-wide pending interviews — split by slot phase when requested.

    phase:
      - scheduled: slot end still in the future (sidebar upcoming list)
      - awaiting_status: slot finished, attendance not logged yet
      - all / None: both groups combined
    """
    from datetime import date, timedelta

    today = date.today()
    forward_end = (today + timedelta(days=max(int(days), 1))).isoformat()
    lookback = max(int(lookback_days), 0)
    range_start = (today - timedelta(days=lookback)).isoformat()
    rows = _interview_rows_for_range(range_start, forward_end)
    rows = _filter_interview_rows(
        rows,
        viewer_reference=viewer_reference,
        filter_attendee=filter_attendee,
        filter_search=filter_search,
        filter_channel=filter_channel,
    )
    scheduled, awaiting = _split_pending_interviews_by_slot_phase(rows)
    phase_key = (phase or "all").strip().lower()
    if phase_key == "scheduled":
        out_rows = scheduled
    elif phase_key in {"awaiting_status", "awaiting", "pending_status"}:
        out_rows = awaiting
    else:
        out_rows = scheduled + awaiting
        out_rows.sort(key=_slot_chronological_sort_key)
    out_rows = _enrich_interview_rows_with_slot_screenshots(out_rows)
    counts = _interview_attendance_counts(out_rows)
    return {
        "from": range_start,
        "to": forward_end,
        "interviews": out_rows,
        "count": len(out_rows),
        "scheduled_count": len(scheduled),
        "awaiting_status_count": len(awaiting),
        **counts,
    }


def public_booked_interview_slots(*, days: int = 60) -> dict:
    """Confirmed interview slots for the public submit page (name + time only)."""
    from datetime import date, timedelta

    today = date.today()
    start = today.isoformat()
    end = (today + timedelta(days=max(int(days), 1))).isoformat()
    rows = _interview_rows_for_range(start, end)
    slots: list[dict] = []
    for row in rows:
        if row_interview_attendance_status(row):
            continue
        slot_date = (row.get("date") or "").strip()[:10]
        slot_time = (row.get("time") or "").strip()
        slot_end = (row.get("time_end") or "").strip()
        if not slot_date or not slot_time:
            continue
        # Show all of today's slots (even if time passed) so user sees just-booked slot
        if slot_date != today.isoformat() and not _interview_slot_still_upcoming(slot_date, slot_time, slot_end):
            continue
        slots.append({
            "name": canonical_candidate_name((row.get("name") or "").strip()),
            "technology": row_candidate_technology(row) or row.get("technology") or "",
            "interview_round": normalise_interview_round(row.get("interview_round")),
            "date": _normalize_iso_date(slot_date),
            "time": slot_time,
            "time_end": slot_end,
        })
    slots.sort(key=_slot_chronological_sort_key)
    return {
        "from": start,
        "to": end,
        "slots": slots,
        "count": len(slots),
    }


def clear_future_interview_attendance(*, by: str = "system") -> int:
    """Reset wrongly-logged attendance on slots after today (restores upcoming list)."""
    from datetime import date

    today = date.today().isoformat()
    data = _load()
    rows = data.get("candidates") or []
    changed = 0
    for i, raw in enumerate(rows):
        slot_date = (raw.get("date") or "").strip()[:10]
        if not slot_date or slot_date <= today:
            continue
        status = row_interview_attendance_status(raw)
        if status not in {"attended", "not_attended"}:
            continue
        r = dict(raw)
        r["interview_attendance_status"] = ""
        r["interview_attended"] = False
        r["interview_attendance_remark"] = ""
        r["interview_attended_at"] = ""
        r["interview_attended_by"] = ""
        r["updated_at"] = _now_iso()
        rows[i] = r
        changed += 1
    if changed:
        data["candidates"] = rows
        _save(data)
    return changed


def interview_global_summary(
    from_date: str,
    to_date: str,
    *,
    viewer_reference: str | None = None,
    filter_attendee: str | None = None,
    filter_search: str | None = None,
    filter_channel: str | None = None,
    filter_round: str | None = None,
    filter_technology: str | None = None,
    include_unconfirmed: bool = False,
    upcoming_only: bool = False,
) -> dict:
    """Ops snapshot — interviews by attendee/referrer/tech + tasks (scoped per viewer)."""
    start = (from_date or "").strip()[:10]
    end = (to_date or "").strip()[:10]
    if len(start) != 10 or len(end) != 10:
        raise ValueError("from and to must be YYYY-MM-DD")
    if start > end:
        start, end = end, start

    rows = _interview_rows_for_range(
        start,
        end,
        include_unconfirmed=include_unconfirmed,
    )
    rows = _filter_interview_rows(
        rows,
        viewer_reference=viewer_reference,
        filter_attendee=filter_attendee,
        filter_search=filter_search,
        filter_channel=filter_channel,
        filter_round=filter_round,
        filter_technology=filter_technology,
    )
    if upcoming_only:
        rows = _filter_upcoming_only_rows(rows)
    interview_counts = _interview_attendance_counts(rows)

    def _empty_bucket() -> dict[str, int]:
        return {
            "scheduled": 0,
            "attended": 0,
            "not_attended": 0,
            "cancelled": 0,
            "rescheduled": 0,
            "pending": 0,
        }

    by_attendee: dict[str, dict[str, int]] = {}
    by_referrer: dict[str, dict[str, int]] = {}
    by_candidate: dict[str, dict[str, int]] = {}
    by_technology: dict[str, dict[str, int]] = {}

    def _bump(bucket: dict[str, dict[str, int]], key: str, status: str) -> None:
        label = (key or "").strip() or "Unknown"
        entry = bucket.setdefault(label, _empty_bucket())
        entry["scheduled"] += 1
        if status == "attended":
            entry["attended"] += 1
        elif status == "not_attended":
            entry["not_attended"] += 1
        elif status == "cancelled":
            entry["cancelled"] += 1
        elif status == "rescheduled":
            entry["rescheduled"] += 1
        else:
            entry["pending"] += 1

    for row in rows:
        status = row_interview_attendance_status(row)
        _bump(by_attendee, row_interview_attendee(row), status)
        _bump(by_referrer, (row.get("reference") or "").strip() or "Unknown", status)
        _bump(by_candidate, canonical_candidate_name((row.get("name") or "").strip()) or "Unknown", status)
        _bump(by_technology, row_candidate_technology(row) or "Unspecified", status)

    def _bucket_rows(bucket: dict[str, dict[str, int]]) -> list[dict]:
        return [
            {"name": name, **stats}
            for name, stats in sorted(
                bucket.items(),
                key=lambda kv: (-kv[1]["scheduled"], kv[0].lower()),
            )
        ]

    from features import operator_tasks_store

    viewer = (viewer_reference or "").strip()
    task_scope = None
    if viewer and not _is_interview_attender_reference(viewer):
        task_scope = viewer

    task_by_handler: dict[str, dict[str, int]] = {}
    task_totals = {"open": 0, "done": 0}
    for task in operator_tasks_store.list_tasks(include_done=True, reference=task_scope):
        day = (task.get("date") or "").strip()[:10]
        if day and (day < start or day > end):
            continue
        handler = (task.get("reference") or "").strip() or "Unknown"
        entry = task_by_handler.setdefault(handler, {"open": 0, "done": 0})
        if task.get("done"):
            entry["done"] += 1
            task_totals["done"] += 1
        else:
            entry["open"] += 1
            task_totals["open"] += 1

    return {
        "from": start,
        "to": end,
        "interviews": {
            "count": len(rows),
            **interview_counts,
            "by_attendee": _bucket_rows(by_attendee),
            "by_referrer": _bucket_rows(by_referrer),
            "by_candidate": _bucket_rows(by_candidate),
            "by_technology": _bucket_rows(by_technology),
        },
        "tasks": {
            **task_totals,
            "by_handler": [
                {"name": name, **stats}
                for name, stats in sorted(
                    task_by_handler.items(),
                    key=lambda kv: (-(kv[1]["open"] + kv[1]["done"]), kv[0].lower()),
                )
            ],
        },
    }


def set_interview_attendance(
    cid: str,
    *,
    status: str = "",
    remark: str = "",
    attended: bool | None = None,
    attendee: str | None = None,
    by: str,
    allow_future: bool = False,
) -> dict | None:
    data = _load()
    rows = data.get("candidates") or []
    for i, r in enumerate(rows):
        if r.get("id") != cid:
            continue
        r = dict(r)
        if attended is not None and not (status or "").strip():
            resolved_status = "attended" if attended else ""
        else:
            resolved_status = normalise_interview_attendance_status(status)
        if (
            not allow_future
            and resolved_status in {"attended", "not_attended"}
            and _interview_slot_is_future(r)
        ):
            raise ValueError("Attendance can only be logged on or after the interview date")
        remark_text = _clean_str(remark)[:500]
        r["interview_attendance_status"] = resolved_status
        r["interview_attended"] = resolved_status == "attended"
        if resolved_status in {"attended", "not_attended"}:
            r["interview_attendance_remark"] = remark_text
            r["interview_attended_at"] = _now_iso()
            r["interview_attended_by"] = (by or "").strip()[:120]
            if attendee is not None:
                try:
                    r["interview_attendee"] = normalise_interview_attendee_name(attendee)
                except ValueError:
                    fallback = row_interview_attendee(r) or "Tool"
                    r["interview_attendee"] = normalise_interview_attendee_name(fallback)
            else:
                r["interview_attendee"] = row_interview_attendee(r)
        elif resolved_status in {"cancelled", "rescheduled"}:
            r["interview_attendance_remark"] = remark_text
            r["interview_attended_at"] = _now_iso()
            r["interview_attended_by"] = (by or "").strip()[:120]
        else:
            r["interview_attendance_remark"] = ""
            r["interview_attended_at"] = ""
            r["interview_attended_by"] = ""
        r["updated_at"] = _now_iso()
        rows[i] = r
        data["candidates"] = rows
        _save(data)
        return _with_computed(r)
    return None


def set_interview_attendee(
    cid: str,
    *,
    attendee: str = "",
    by: str = "",
) -> dict | None:
    data = _load()
    rows = data.get("candidates") or []
    for i, r in enumerate(rows):
        if r.get("id") != cid:
            continue
        r = dict(r)
        r["interview_attendee"] = normalise_interview_attendee_name(attendee)
        r["updated_at"] = _now_iso()
        rows[i] = r
        data["candidates"] = rows
        _save(data)
        return _with_computed(r)
    return None


def roster_csv_rows(rows: list[dict]) -> str:
    """Excel-friendly CSV: #, Name, Technology — quoted fields, sorted by tech then name."""
    import csv
    import io

    sorted_rows = sorted(
        rows,
        key=lambda r: (
            canonical_technology(r.get("technology") or "").lower(),
            (r.get("name") or "").strip().lower(),
        ),
    )
    buf = io.StringIO()
    writer = csv.writer(
        buf,
        lineterminator="\r\n",
        quoting=csv.QUOTE_ALL,
    )
    writer.writerow(["#", "Name", "Technology"])
    for idx, row in enumerate(sorted_rows, start=1):
        writer.writerow([
            idx,
            (row.get("name") or "").strip(),
            canonical_technology(row.get("technology") or ""),
        ])
    return buf.getvalue()


def get_candidate(cid: str) -> dict | None:
    reconcile_resume_metadata()
    for r in _load().get("candidates") or []:
        if r.get("id") == cid:
            return _with_computed(r)
    return None


def find_by_telegram(slot: str, user_id: int) -> dict | None:
    """Find a candidate row linked to a Telegram DM thread."""
    slot = (slot or "").strip()
    try:
        uid = int(user_id)
    except (TypeError, ValueError):
        return None
    if not slot or uid <= 0:
        return None
    for row in _load().get("candidates") or []:
        if (row.get("telegram_slot") or "").strip() != slot:
            continue
        try:
            row_uid = int(row.get("telegram_user_id") or 0)
        except (TypeError, ValueError):
            row_uid = 0
        if row_uid == uid:
            return _with_computed(row)
    return None


def create_candidate(record: dict, *, allow_slot_without_rules: bool = False) -> dict:
    data = _load()
    row = _normalise(record)
    if row.get("slot_confirmed") and not allow_slot_without_rules:
        reason = slot_confirm_block_reason(row)
        if reason:
            raise ValueError(reason)
    data.setdefault("candidates", []).append(row)
    _save(data)
    return _with_computed(row)


def _validate_interview_slot_times(start: str, end: str) -> None:
    slot_start = _clean_str(start)
    slot_end = _clean_str(end)
    if not slot_start:
        raise ValueError("Interview start time is required")
    if not slot_end:
        raise ValueError("Interview end time is required")
    if _interview_time_sort_key(slot_end)[0] <= _interview_time_sort_key(slot_start)[0]:
        raise ValueError("End time must be after start time")


def create_interview_slot(
    *,
    name: str,
    date: str,
    time: str,
    time_end: str = "",
    technology: str = "",
    reference: str = "",
    phone: str = "",
    notes: str = "",
    interview_round: str = "",
    interview_attendee: str = "",
) -> dict:
    """Minimal ops shortcut — name, date, time (+ optional tech/ref). Slot is confirmed immediately."""
    name = canonical_candidate_name(_clean_str(name))
    if not name:
        raise ValueError("Candidate name is required")
    day = _clean_str(date)[:10]
    if len(day) != 10:
        raise ValueError("Interview date is required (YYYY-MM-DD)")
    slot_time = _clean_str(time)
    _validate_interview_slot_times(slot_time, time_end)
    attendee = normalise_interview_attendee_name(interview_attendee) if interview_attendee else infer_interview_attendee(technology, name)
    tech = canonical_technology(_clean_str(technology))
    if tech in {"", "Unspecified"} and candidate_defaults_to_tool_attendee(name):
        tech = TOOL_PROFILE_CANDIDATE_TECHNOLOGY
    record = {
        "name": name,
        "date": day,
        "time": slot_time,
        "time_end": _clean_str(time_end),
        "technology": tech,
        "reference": _canonical_reference_name(_clean_str(reference)),
        "phone": _clean_str(phone),
        "notes": _clean_str(notes),
        "interview_attendee": attendee,
        "interview_round": normalise_interview_round(interview_round),
        "service_type": "round_wise",
        "interview_scope": "external",
        "stage": "in_progress",
        "task": "in_progress",
        "slot_confirmed": True,
        "slots_group_posted": True,
    }
    return create_candidate(record, allow_slot_without_rules=True)


def _candidate_has_confirmed_slot(row: dict) -> bool:
    if not _coerce_bool(row.get("slot_confirmed")):
        return False
    day = _clean_str(row.get("date"))[:10]
    return len(day) == 10


def _duplicate_candidate_slot(
    source: dict,
    *,
    date: str,
    time: str,
    time_end: str = "",
    notes: str = "",
    interview_round: str = "",
    interview_attendee: str | None = None,
) -> dict:
    """Clone an in-progress candidate so a second interview slot keeps prior rows."""
    existing_service = _normalise_service_type(source.get("service_type"), source)
    attendee = ""
    if interview_attendee is not None:
        attendee = normalise_interview_attendee_name(interview_attendee)
    else:
        attendee = row_interview_attendee(source)

    record = {
        "name": source.get("name"),
        "technology": source.get("technology"),
        "phone": source.get("phone"),
        "reference": source.get("reference"),
        "consultancy": source.get("consultancy"),
        "service_type": existing_service,
        "interview_scope": source.get("interview_scope")
        or ("external" if existing_service == "round_wise" else ""),
        "purpose": source.get("purpose"),
        "payment": source.get("payment"),
        "expected_payment": source.get("expected_payment"),
        "task": "in_progress",
        "stage": "in_progress",
        "date": date,
        "logged_date": _row_lead_date(source),
        "time": time,
        "time_end": _clean_str(time_end),
        "notes": _clean_str(notes),
        "interview_attendee": attendee,
        "interview_round": normalise_interview_round(interview_round) or normalise_interview_round(source.get("interview_round")),
        "slot_confirmed": True,
        "slots_group_posted": True,
        "interview_attendance_status": "",
        "interview_attended": False,
        "proofs": [
            p for p in (source.get("proofs") or [])
            if not _is_slot_screenshot_proof(p)
        ],
        "resumes": list(source.get("resumes") or []),
    }
    return create_candidate(record, allow_slot_without_rules=True)


def assign_interview_slot(
    *,
    candidate_id: str,
    date: str,
    time: str,
    time_end: str = "",
    notes: str = "",
    interview_round: str = "",
    interview_attendee: str | None = None,
) -> dict:
    """Schedule an existing candidate — first slot updates the record; later slots clone."""
    cid = _clean_str(candidate_id)
    if not cid:
        raise ValueError("Select a candidate")
    existing = get_candidate(cid)
    if not existing:
        raise ValueError("Candidate not found")
    day = _clean_str(date)[:10]
    if len(day) != 10:
        raise ValueError("Interview date is required (YYYY-MM-DD)")
    slot_time = _clean_str(time)
    _validate_interview_slot_times(slot_time, time_end)

    if _candidate_has_confirmed_slot(existing):
        return _duplicate_candidate_slot(
            existing,
            date=day,
            time=slot_time,
            time_end=time_end,
            notes=notes,
            interview_round=interview_round,
            interview_attendee=interview_attendee,
        )

    existing_service = _normalise_service_type(existing.get("service_type"), existing)
    patch: dict = {
        "time": slot_time,
        "time_end": _clean_str(time_end),
        "service_type": existing_service,
        "interview_scope": existing.get("interview_scope") or ("external" if existing_service == "round_wise" else ""),
        "stage": "in_progress",
        "task": "in_progress",
        "slot_confirmed": True,
        "slots_group_posted": True,
    }
    logged = _clean_str(existing.get("logged_date"))[:10]
    existing_day = _clean_str(existing.get("date"))[:10]
    if len(logged) != 10:
        # Preserve the original date before overwriting with slot day.
        # Use existing date if available, otherwise fall back to created_at.
        if len(existing_day) == 10:
            patch["logged_date"] = existing_day
        else:
            created = _clean_str(existing.get("created_at"))[:10]
            if len(created) == 10:
                patch["logged_date"] = created
    patch["date"] = day
    extra = sanitize_candidate_notes(_clean_str(notes))
    if extra:
        prev = _clean_str(existing.get("notes"))
        patch["notes"] = f"{prev}\n{extra}".strip() if prev else extra
    if interview_attendee is not None:
        patch["interview_attendee"] = normalise_interview_attendee_name(interview_attendee)
    else:
        patch["interview_attendee"] = row_interview_attendee(existing)
    rnd = normalise_interview_round(interview_round)
    if rnd:
        patch["interview_round"] = rnd
    return update_candidate(cid, patch, allow_slot_without_rules=True)


def update_interview_slot(
    *,
    candidate_id: str,
    date: str,
    time: str,
    time_end: str = "",
    notes: str = "",
    interview_round: str = "",
    interview_attendee: str | None = None,
) -> dict:
    """Reschedule an existing confirmed slot — updates date/time and optional notes."""
    cid = _clean_str(candidate_id)
    if not cid:
        raise ValueError("Candidate is required")
    existing = get_candidate(cid)
    if not existing:
        raise ValueError("Candidate not found")
    if not _coerce_bool(existing.get("slot_confirmed")):
        raise ValueError("This candidate has no confirmed interview slot")
    day = _clean_str(date)[:10]
    if len(day) != 10:
        raise ValueError("Interview date is required (YYYY-MM-DD)")
    slot_time = _clean_str(time)
    _validate_interview_slot_times(slot_time, time_end)
    patch: dict = {
        "date": day,
        "time": slot_time,
        "time_end": _clean_str(time_end),
        "slot_confirmed": True,
        "slots_group_posted": True,
    }
    if notes is not None:
        patch["notes"] = sanitize_candidate_notes(_clean_str(notes))
    if interview_attendee is not None:
        patch["interview_attendee"] = normalise_interview_attendee_name(interview_attendee)
    elif candidate_defaults_to_tool_attendee(existing.get("name") or ""):
        patch["interview_attendee"] = "Tool"
    rnd = normalise_interview_round(interview_round)
    if rnd:
        patch["interview_round"] = rnd
    return update_candidate(cid, patch, allow_slot_without_rules=True)


def cancel_confirmed_interview_slot_by_name(
    name: str,
    *,
    date: str = "",
    time: str = "",
    source: str = "public-upload",
    slot_image: bytes | None = None,
    slot_image_name: str = "",
    slot_image_mime: str = "",
) -> tuple[dict, str]:
    """Cancel a booked slot for a profile candidate matched by name (optional date/time hints)."""
    canon = canonical_candidate_name(_clean_str(name))
    if not canon:
        raise ValueError("Candidate name is required")

    rows = list_candidates(stage="all", month="all")
    key = _normalise_candidate_name_key(canon)
    confirmed = [
        r for r in rows
        if _normalise_candidate_name_key(r.get("name") or "") == key
        and _candidate_has_confirmed_slot(r)
    ]
    if not confirmed:
        raise ValueError(f"No booked interview slot found for {canon}.")

    day = _clean_str(date)[:10]
    slot_time = _clean_str(time)[:5]
    target: dict | None = None
    if day and slot_time:
        target = _find_existing_slot_row(rows, canon, day, slot_time)
    if target is None and day:
        same_day = [r for r in confirmed if (r.get("date") or "")[:10] == day]
        if len(same_day) == 1:
            target = same_day[0]
        elif slot_time:
            for row in same_day:
                if (_clean_str(row.get("time") or "")[:5]) == slot_time:
                    target = row
                    break
    if target is None and len(confirmed) == 1:
        target = confirmed[0]
    if target is None:
        raise ValueError(
            f"{canon} has multiple booked slots — upload a screenshot that clearly shows the date and time being cancelled."
        )

    row = cancel_interview_slot(candidate_id=str(target["id"]))
    if slot_image and row.get("id"):
        attach_public_slot_screenshot(
            str(row["id"]),
            data=slot_image,
            original_name=slot_image_name or "slot-cancellation.jpg",
            mime_type=slot_image_mime or "image/jpeg",
            source=f"Cancellation screenshot · {source}",
        )
        row = get_candidate(str(row["id"])) or row
    return row, "cancelled"


def _pick_confirmed_slot_for_name(
    name: str,
    *,
    date: str = "",
    time: str = "",
    prefer_ended: bool = False,
) -> dict:
    """Resolve one confirmed slot row for cancel / reschedule / session-complete."""
    canon = canonical_candidate_name(_clean_str(name))
    if not canon:
        raise ValueError("Candidate name is required")

    rows = list_candidates(stage="all", month="all")
    key = _normalise_candidate_name_key(canon)
    confirmed = [
        r for r in rows
        if _normalise_candidate_name_key(r.get("name") or "") == key
        and _candidate_has_confirmed_slot(r)
    ]
    if not confirmed:
        raise ValueError(f"No booked interview slot found for {canon}.")

    day = _clean_str(date)[:10]
    slot_time = _clean_str(time)[:5]
    target: dict | None = None
    if day and slot_time:
        target = _find_existing_slot_row(rows, canon, day, slot_time)
    if target is None and day:
        same_day = [r for r in confirmed if (r.get("date") or "")[:10] == day]
        if len(same_day) == 1:
            target = same_day[0]
        elif slot_time:
            for row in same_day:
                if (_clean_str(row.get("time") or "")[:5]) == slot_time:
                    target = row
                    break
    if target is None and len(confirmed) == 1:
        target = confirmed[0]
    if target is None and prefer_ended:
        ended = [
            r for r in confirmed
            if not _interview_slot_still_upcoming(
                (r.get("date") or "")[:10],
                r.get("time") or "",
                r.get("time_end") or "",
            )
        ]
        if len(ended) == 1:
            target = ended[0]
        elif ended:
            ended.sort(key=_slot_chronological_sort_key)
            target = ended[-1]
    if target is None:
        raise ValueError(
            f"{canon} has multiple booked slots — pick the slot on submit-slot or include date/time in the screenshot."
        )
    return target


def reschedule_confirmed_interview_slot_by_name(
    name: str,
    *,
    date: str,
    time: str,
    time_end: str = "",
    interview_round: str = "",
    notes: str = "",
    source: str = "public-upload",
    slot_image: bytes | None = None,
    slot_image_name: str = "",
    slot_image_mime: str = "",
) -> tuple[dict, str]:
    """Move an existing booked slot to a new date/time from a reschedule screenshot."""
    canon = canonical_candidate_name(_clean_str(name))
    if not canon:
        raise ValueError("Candidate name is required")

    slot_time = _clean_str(time)
    if not slot_time:
        raise ValueError("New interview time is required")

    target = _pick_confirmed_slot_for_name(canon)
    day = _clean_str(date)[:10]
    if len(day) != 10:
        day = (target.get("date") or "")[:10]
    if len(day) != 10:
        raise ValueError("Include the new date (e.g. tomorrow) or use submit-slot with an invite screenshot.")

    slot_end = _default_slot_time_end(slot_time, time_end)
    _validate_interview_slot_times(slot_time, slot_end)

    _resolve_public_slot_conflicts(
        candidate_name=canon,
        date=day,
        time=slot_time,
        time_end=slot_end,
        exclude_candidate_id=str(target["id"]),
    )
    note = sanitize_candidate_notes(_clean_str(notes))
    row = update_interview_slot(
        candidate_id=str(target["id"]),
        date=day,
        time=slot_time,
        time_end=slot_end,
        notes=note,
        interview_round=interview_round or normalise_interview_round(target.get("interview_round")),
    )
    if slot_image and row.get("id"):
        attach_public_slot_screenshot(
            str(row["id"]),
            data=slot_image,
            original_name=slot_image_name or "slot-reschedule.jpg",
            mime_type=slot_image_mime or "image/jpeg",
            source=f"Reschedule screenshot · {source}",
        )
        row = get_candidate(str(row["id"])) or row
    return row, "rescheduled"


def mark_session_complete_by_name(
    name: str,
    *,
    date: str = "",
    time: str = "",
    source: str = "public-upload",
    slot_image: bytes | None = None,
    slot_image_name: str = "",
    slot_image_mime: str = "",
) -> tuple[dict, str]:
    """Mark attended from a Session complete screenshot."""
    canon = canonical_candidate_name(_clean_str(name))
    target = _pick_confirmed_slot_for_name(
        canon,
        date=date,
        time=time,
        prefer_ended=True,
    )
    row = set_interview_attendance(
        str(target["id"]),
        status="attended",
        remark="Session complete screenshot",
        by="submit-slot",
    )
    if not row:
        raise ValueError("Could not update attendance for this candidate.")
    if slot_image and row.get("id"):
        attach_public_slot_screenshot(
            str(row["id"]),
            data=slot_image,
            original_name=slot_image_name or "session-complete.jpg",
            mime_type=slot_image_mime or "image/jpeg",
            source=f"Session complete · {source}",
        )
        row = get_candidate(str(row["id"])) or row
    return row, "attended"


def cancel_interview_slot(*, candidate_id: str) -> dict:
    """Remove a confirmed slot from the roster without deleting the candidate."""
    cid = _clean_str(candidate_id)
    if not cid:
        raise ValueError("Candidate is required")
    data = _load()
    rows = data.get("candidates") or []
    for i, r in enumerate(rows):
        if r.get("id") != cid:
            continue
        r = dict(r)
        r["date"] = ""
        r["time"] = ""
        r["time_end"] = ""
        r["slot_confirmed"] = False
        r["slot_confirmed_at"] = ""
        r["interview_attendance_status"] = ""
        r["interview_attended"] = False
        r["interview_attendance_remark"] = ""
        r["interview_attended_at"] = ""
        r["interview_attended_by"] = ""
        r["updated_at"] = _now_iso()
        rows[i] = r
        data["candidates"] = rows
        _save(data)
        return _with_computed(r)
    raise ValueError("Candidate not found")


def _default_slot_time_end(start: str, end: str = "") -> str:
    """Use parsed end, or start + 30 minutes when end is missing or invalid."""
    start = _clean_str(start)
    end = _clean_str(end)
    if end and end != start:
        try:
            sh, sm = map(int, start.split(":"))
            eh, em = map(int, end.split(":"))
            if (eh, em) > (sh, sm):
                return end
        except ValueError:
            pass
    try:
        sh, sm = map(int, start.split(":"))
    except ValueError:
        return start
    total = sh * 60 + sm + 30
    return f"{(total // 60) % 24:02d}:{total % 60:02d}"


def _find_existing_slot_row(rows: list[dict], name: str, date: str, time: str) -> dict | None:
    canon = canonical_candidate_name(name)
    key = _normalise_candidate_name_key(canon)
    day = _clean_str(date)[:10]
    slot_time = _clean_str(time)[:5]
    for row in rows:
        if _normalise_candidate_name_key(row.get("name") or "") != key:
            continue
        if (row.get("date") or "")[:10] != day:
            continue
        if (_clean_str(row.get("time") or "")[:5]) != slot_time:
            continue
        return row
    return None


def _find_assignable_profile_row(rows: list[dict], name: str) -> dict | None:
    """Profile row without a confirmed slot — must have a scheduled interview date."""
    key = _normalise_candidate_name_key(canonical_candidate_name(name))
    matches: list[dict] = []
    for row in rows:
        if _normalise_candidate_name_key(row.get("name") or "") != key:
            continue
        if _normalise_service_type(row.get("service_type"), row) == "round_wise":
            continue
        if _candidate_has_confirmed_slot(row):
            continue
        matches.append(row)
    if not matches:
        return None
    return matches[0]


def attach_public_slot_screenshot(
    candidate_id: str,
    *,
    data: bytes,
    original_name: str = "",
    mime_type: str = "",
    source: str = "public-upload",
) -> dict | None:
    """Save the candidate's slot confirmation screenshot on their roster row."""
    cid = _clean_str(candidate_id)
    if not cid or not data:
        return None
    caption = f"Interview slot screenshot · {source}"[:200]
    entry = add_proof(
        cid,
        data=data,
        original_name=original_name or "slot-screenshot.jpg",
        mime_type=mime_type or "image/jpeg",
        note=caption,
    )
    if not entry:
        return None
    cdata = _load()
    rows = cdata.get("candidates") or []
    idx = next((i for i, r in enumerate(rows) if r.get("id") == cid), -1)
    if idx >= 0:
        rows[idx]["slot_screenshot_proof_id"] = entry["id"]
        rows[idx]["updated_at"] = _now_iso()
        cdata["candidates"] = rows
        _save(cdata)
    return entry


def _finish_public_slot_import(
    row: dict,
    action: str,
    *,
    technology: str = "",
    interview_round: str = "",
    slot_image: bytes | None = None,
    slot_image_name: str = "",
    slot_image_mime: str = "",
    source: str = "public-upload",
) -> tuple[dict, str]:
    tech = canonical_technology(_clean_str(technology))
    if tech and tech not in {"", "Unspecified"}:
        existing = row_candidate_technology(row) or (row.get("technology") or "")
        if not str(existing).strip() or str(existing).strip() in {"", "Unspecified"}:
            row = update_candidate(str(row["id"]), {"technology": tech}, allow_slot_without_rules=True)
    rnd = normalise_interview_round(interview_round)
    if rnd and row.get("id"):
        row = update_candidate(
            str(row["id"]),
            {"interview_round": rnd},
            allow_slot_without_rules=True,
        )
    if slot_image and row.get("id"):
        attach_public_slot_screenshot(
            str(row["id"]),
            data=slot_image,
            original_name=slot_image_name,
            mime_type=slot_image_mime,
            source=source,
        )
        row = get_candidate(str(row["id"])) or row
    return row, action


def import_confirmed_interview_slot(
    *,
    name: str,
    date: str,
    time: str,
    time_end: str = "",
    notes: str = "",
    technology: str = "",
    interview_round: str = "",
    service_type: str = "round_wise",
    source: str = "public-upload",
    payment_proof_id: str | None = None,
    slot_image: bytes | None = None,
    slot_image_name: str = "",
    slot_image_mime: str = "",
) -> tuple[dict, str]:
    """Create or assign a confirmed interview slot for a profile candidate."""
    canon = canonical_candidate_name(_clean_str(name))
    if not canon:
        raise ValueError("Candidate name is required")
    if excluded_from_public_slot_booking(canon):
        raise ValueError(f"{canon} is no longer booking interview slots.")

    pay_block = slot_booking_payment_block_reason(canon, payment_proof_id=payment_proof_id)
    if pay_block:
        due = merged_balance_due_for_name(canon)
        raise PaymentDueError(name=canon, balance_due=due, needs_proof=not payment_proof_id)

    day = _clean_str(date)[:10]
    if len(day) != 10:
        raise ValueError("Interview date is required (YYYY-MM-DD)")
    slot_time = _clean_str(time)
    slot_end = _default_slot_time_end(slot_time, time_end)
    _validate_interview_slot_times(slot_time, slot_end)

    tech = canonical_technology(_clean_str(technology))
    rnd = normalise_interview_round(interview_round)
    if "Candidate" in source and not rnd:
        raise ValueError("Select the interview round (L1, L2, etc.)")

    rows = list_candidates(stage="all", month="all")
    existing = _find_existing_slot_row(rows, canon, day, slot_time)
    if existing and _candidate_has_confirmed_slot(existing):
        patch: dict = {}
        existing_end = _clean_str(existing.get("time_end"))
        if slot_end and slot_end != existing_end:
            patch["time_end"] = slot_end
        if rnd and rnd != normalise_interview_round(existing.get("interview_round")):
            patch["interview_round"] = rnd
        if patch:
            existing = update_candidate(str(existing["id"]), patch, allow_slot_without_rules=True)
        return _finish_public_slot_import(
            existing,
            "skip_exists" if not patch else "updated",
            technology=tech,
            interview_round=rnd,
            slot_image=slot_image,
            slot_image_name=slot_image_name,
            slot_image_mime=slot_image_mime,
            source=source,
        )

    _resolve_public_slot_conflicts(
        candidate_name=canon,
        date=day,
        time=slot_time,
        time_end=slot_end,
    )

    note = sanitize_candidate_notes(_clean_str(notes))

    if existing and not _candidate_has_confirmed_slot(existing):
        row = assign_interview_slot(
            candidate_id=existing["id"],
            date=day,
            time=slot_time,
            time_end=slot_end,
            notes=note,
            interview_round=rnd,
        )
        return _finish_public_slot_import(
            row,
            "assigned",
            technology=tech,
            interview_round=rnd,
            slot_image=slot_image,
            slot_image_name=slot_image_name,
            slot_image_mime=slot_image_mime,
            source=source,
        )

    profile_row = _find_assignable_profile_row(rows, canon)
    if profile_row:
        row = assign_interview_slot(
            candidate_id=profile_row["id"],
            date=day,
            time=slot_time,
            time_end=slot_end,
            notes=note,
            interview_round=rnd,
        )
        return _finish_public_slot_import(
            row,
            "assigned_profile",
            technology=tech,
            interview_round=rnd,
            slot_image=slot_image,
            slot_image_name=slot_image_name,
            slot_image_mime=slot_image_mime,
            source=source,
        )

    occupied = next(
        (
            r for r in rows
            if _normalise_candidate_name_key(r.get("name") or "") == _normalise_candidate_name_key(canon)
            and _candidate_has_confirmed_slot(r)
        ),
        None,
    )
    if occupied:
        row = _duplicate_candidate_slot(
            occupied,
            date=day,
            time=slot_time,
            time_end=slot_end,
            notes=note,
            interview_round=rnd,
        )
        return _finish_public_slot_import(
            row,
            "cloned",
            technology=tech,
            interview_round=rnd,
            slot_image=slot_image,
            slot_image_name=slot_image_name,
            slot_image_mime=slot_image_mime,
            source=source,
        )

    # Never create a candidate or a confirmed Daily Ops slot from an unmatched
    # public/import name.  A real candidate must exist first; otherwise a
    # malformed upload can silently book someone who has no interview.
    # EXCEPTION: for preset slot bookers (PUBLIC_SLOT_BOOKER_NAMES), auto-create
    # a candidate record so recurring users like Keerthana aren't blocked.
    canon_key = _normalise_candidate_name_key(canon)
    is_preset = any(
        _normalise_candidate_name_key(n) == canon_key
        for n in PUBLIC_SLOT_BOOKER_NAMES
    )
    if is_preset:
        # Auto-create candidate for this preset booker (round-wise only)
        auto_tech = row_candidate_technology({"name": canon})
        auto_ref = "Thrilok"  # default reference for preset bookers
        new_candidate = create_candidate({
            "name": canon,
            "technology": auto_tech or "Unspecified",
            "reference": auto_ref,
            "stage": "in_progress",
            "date": day,
            "logged_date": day,
            "time": slot_time,
            "time_end": slot_end,
            "notes": note,
            "interview_round": rnd,
            "service_type": service_type or "round_wise",
        })
        return _finish_public_slot_import(
            new_candidate,
            "auto_created",
            technology=auto_tech,
            interview_round=rnd,
            slot_image=slot_image,
            slot_image_name=slot_image_name,
            slot_image_mime=slot_image_mime,
            source=source,
        )

    raise ValueError(
        f"No existing candidate matched {canon}. Add/select the candidate before booking an interview slot."
    )


def _slot_picker_dedupe_key(row: dict) -> str:
    return _normalise_candidate_name_key(
        canonical_candidate_name((row.get("name") or "").strip())
    )


def _slot_picker_row_score(row: dict, *, prefer_react_js: bool = False) -> tuple:
    """Prefer React JS profile, then rows without a date, then contact/payment."""
    tech = _technology_key(row_candidate_technology(row) or "")
    react_js = 1 if prefer_react_js and tech == "react js" else 0
    has_date = 1 if (row.get("date") or "").strip() else 0
    has_phone = 1 if (row.get("phone") or "").strip() else 0
    payment = int(row.get("payment") or 0)
    return (react_js, 0 if has_date else 1, has_phone, payment)


def _public_slot_booking_excluded_keys() -> frozenset[str]:
    return frozenset(
        _normalise_candidate_name_key(canonical_candidate_name(n))
        for n in PUBLIC_SLOT_BOOKING_EXCLUDED
    )


def excluded_from_public_slot_booking(name: str) -> bool:
    key = _normalise_candidate_name_key(canonical_candidate_name(_clean_str(name)))
    return key in _public_slot_booking_excluded_keys()


def resolve_public_slot_candidate_from_hint(hint: str) -> tuple[str | None, str]:
    """Map WhatsApp display name / caption to a single public slot booker name."""
    raw = re.sub(r"^~\s*", "", _clean_str(hint))
    if not raw:
        return None, "Could not identify candidate — use the submit-slot link and pick your name."

    direct = canonical_candidate_name(raw)
    if direct and not excluded_from_public_slot_booking(direct):
        for preset in PUBLIC_SLOT_BOOKER_NAMES:
            if _normalise_candidate_name_key(preset) == _normalise_candidate_name_key(direct):
                return canonical_candidate_name(preset), ""

    matches: list[str] = []
    lower = raw.lower()
    for hint_key, name_parts in _CANDIDATE_SEARCH_HINTS.items():
        if len(hint_key) >= 4 and hint_key in lower:
            for preset in PUBLIC_SLOT_BOOKER_NAMES:
                if excluded_from_public_slot_booking(preset):
                    continue
                pk = _normalise_candidate_name_key(preset)
                if any(part in pk for part in name_parts):
                    matches.append(canonical_candidate_name(preset))
    for preset in PUBLIC_SLOT_BOOKER_NAMES:
        if excluded_from_public_slot_booking(preset):
            continue
        if candidate_matches_search(preset, raw):
            matches.append(canonical_candidate_name(preset))
    uniq = []
    seen: set[str] = set()
    for name in matches:
        key = _normalise_candidate_name_key(name)
        if key and key not in seen:
            seen.add(key)
            uniq.append(name)
    if len(uniq) == 1:
        return uniq[0], ""
    if len(uniq) > 1:
        return None, (
            f"Multiple candidates match “{raw}”. "
            f"Book via https://teleautomation.online/submit-slot and select your name."
        )
    return None, (
        f"Could not match “{raw}” to a candidate. "
        "Use https://teleautomation.online/submit-slot and pick your name from the list."
    )


def interview_slot_picker_rows(
    *,
    reference: str | None = None,
    attendee_reference: str | None = None,
    channel: str | None = None,
) -> list[dict]:
    """In-progress candidates for the slot dropdown — one entry per profile name."""
    rows = list_candidates(stage="in_progress", month="all", reference=reference)
    ch = (channel or "").strip().lower()
    profile_channel = ch in {"", "profile", "profile_service"}
    if ch == "round_wise":
        rows = [
            r for r in rows
            if _normalise_service_type(r.get("service_type"), r) == "round_wise"
        ]
    elif profile_channel:
        rows = [
            r for r in rows
            if _normalise_service_type(r.get("service_type"), r) != "round_wise"
        ]
    viewer = (attendee_reference or "").strip()
    if viewer and _is_interview_attender_reference(viewer):
        key = viewer.lower()
        rows = [
            r for r in rows
            if _reference_key(row_interview_attendee(r)) == key
        ]

    best: dict[str, dict] = {}
    for row in rows:
        if excluded_from_public_slot_booking(row.get("name") or ""):
            continue
        dedupe = _slot_picker_dedupe_key(row)
        prev = best.get(dedupe)
        score = _slot_picker_row_score(row, prefer_react_js=profile_channel)
        if prev is None or score > _slot_picker_row_score(prev, prefer_react_js=profile_channel):
            best[dedupe] = row
    rows = list(best.values())
    rows.sort(key=lambda r: (r.get("name") or "").lower())
    out: list[dict] = []
    for r in rows:
        canon = canonical_candidate_name((r.get("name") or "").strip())
        due = merged_balance_due_for_name(canon)
        # If candidate already has payment proofs on file, don't block slot booking
        has_proofs = bool(r.get("proofs")) and len(r.get("proofs", [])) > 0
        out.append({
            "id": r.get("id"),
            "name": canon,
            "technology": row_candidate_technology(r) or r.get("technology") or "",
            "phone": r.get("phone") or "",
            "date": r.get("date") or "",
            "time": r.get("time") or "",
            "service_type": r.get("service_type") or "",
            "balance_due": due,
            "needs_payment_proof": due > 0 and not has_proofs,
            "payment_blocked": False,
        })
    out.sort(key=lambda r: (r.get("name") or "").lower())
    return out


def interview_candidate_filter_options(
    *,
    from_date: str | None = None,
    to_date: str | None = None,
    channel: str | None = None,
    viewer_reference: str | None = None,
    filter_attendee: str | None = None,
) -> list[dict]:
    """Unique candidate names for roster filters — same store rows as interview monitor."""
    start = (from_date or "").strip()[:10]
    end = (to_date or "").strip()[:10]
    if len(start) == 10 and len(end) == 10:
        rows = _interview_rows_for_range(start, end)
        rows = _filter_interview_rows(
            rows,
            viewer_reference=viewer_reference,
            filter_attendee=filter_attendee,
            filter_channel=channel,
        )
    else:
        rows = [
            _with_computed(raw)
            for raw in (_load().get("candidates") or [])
            if raw.get("stage") == "in_progress"
        ]
        rows = _filter_interview_rows(
            rows,
            viewer_reference=viewer_reference,
            filter_attendee=filter_attendee,
            filter_channel=channel,
        )

    seen: set[str] = set()
    options: list[dict] = []
    for row in rows:
        display = canonical_candidate_name((row.get("name") or "").strip())
        if not display:
            continue
        key = _normalise_candidate_name_key(display)
        if key in seen:
            continue
        seen.add(key)
        options.append({"value": display, "label": display})

    options.sort(key=lambda item: item["label"].lower())
    return options


def update_candidate(
    cid: str,
    patch: dict,
    *,
    allow_slot_without_rules: bool = False,
) -> dict | None:
    data = _load()
    rows = data.get("candidates") or []
    for i, r in enumerate(rows):
        if r.get("id") == cid:
            allowed_patch = {k: v for k, v in patch.items() if k in _ALLOWED_FIELDS}
            preview = _normalise(allowed_patch, existing=r)
            if preview.get("slot_confirmed") and not _coerce_bool(r.get("slot_confirmed")):
                if not allow_slot_without_rules:
                    reason = slot_confirm_block_reason(_with_computed(preview))
                    if reason:
                        raise ValueError(reason)
            rows[i] = _normalise(allowed_patch, existing=r)
            data["candidates"] = rows
            _save(data)
            return _with_computed(rows[i])
    return None


def delete_candidate(cid: str) -> bool:
    data = _load()
    before = data.get("candidates") or []
    after = [r for r in before if r.get("id") != cid]
    if len(after) == len(before):
        return False
    data["candidates"] = after
    _save(data)
    return True


def _row_month(row: dict) -> str:
    """Extract a 'YYYY-MM' bucket from a row's lead date. Empty string if the
    date is missing or unparseable — those rows go into the 'undated' bin
    and only show up when month filter is 'all'."""
    raw = _row_lead_date(row)
    if not raw:
        return ""
    # Already normalised on insert (YYYY-MM-DD) so a slice is enough.
    if len(raw) >= 7 and raw[4] == "-":
        return raw[:7]
    return ""


def _row_display_month(row: dict) -> str:
    """Month the candidate was registered (logged_date).

    Slot booking must NOT move a candidate to a different month.
    Uses logged_date (when the lead was first added) as the canonical month.
    Falls back to date only if logged_date is not available.
    """
    logged = _clean_str(row.get("logged_date"))[:10]
    if len(logged) >= 7 and logged[4] == "-":
        return logged[:7]
    # Fallback to date if logged_date missing
    visible = _clean_str(row.get("date"))[:10]
    if len(visible) >= 7 and visible[4] == "-":
        return visible[:7]
    return ""


def _row_in_month(row: dict, month: str) -> bool:
    """Match only the visible display date (the 'date' column in the table).

    The month filter should show/hide rows based on what the user sees
    in the Date column — not internal logged_date metadata.
    """
    if not month or month == "all":
        return True
    return _row_display_month(row) == month


def _handler_reference_options(
    all_rows: list[dict],
    *,
    month: str | None,
    scope_key: str | None = None,
) -> list[dict]:
    """All distinct referrers for handler filter dropdowns.

    Includes handlers with zero candidates in the active month so admins can
    still pick any referrer while a month filter is applied."""
    month_rows = all_rows
    if month and month != "all":
        month_rows = [r for r in all_rows if _row_in_month(r, month)]

    # The filter badge must describe the same consolidated profile rows that
    # the Candidates table renders.  Counting raw interview-slot duplicates
    # here made labels such as "Pavan Kalyan · 4" disagree with a 3-row table.
    month_rows = _collapse_profile_candidates(month_rows)

    month_counts: dict[str, int] = {}
    for r in month_rows:
        ref_raw = (r.get("reference") or "").strip()
        if not ref_raw or ref_raw.lower() == "unknown":
            continue
        name = _canonical_reference_name(ref_raw)
        key = _reference_key(name)
        month_counts[key] = month_counts.get(key, 0) + 1

    display_names: dict[str, str] = {}
    total_counts: dict[str, int] = {}
    for preset in HANDLER_REFERENCE_PRESETS:
        name = _canonical_reference_name(preset)
        if not name:
            continue
        key = _reference_key(name)
        display_names[key] = name
        total_counts.setdefault(key, 0)
    for r in _collapse_profile_candidates(all_rows):
        ref_raw = (r.get("reference") or "").strip()
        if not ref_raw or ref_raw.lower() == "unknown":
            continue
        name = _canonical_reference_name(ref_raw)
        key = _reference_key(name)
        display_names[key] = _prefer_reference_display(display_names.get(key, name), ref_raw)
        total_counts[key] = total_counts.get(key, 0) + 1

    keys = list(display_names.keys())
    if scope_key:
        keys = [k for k in keys if k == scope_key]

    options = [
        {
            "name": display_names[key],
            "month_count": month_counts.get(key, 0),
            "total_count": total_counts.get(key, 0),
        }
        for key in keys
    ]
    options.sort(
        key=lambda item: (
            -item["month_count"],
            -item["total_count"],
            item["name"].lower(),
        ),
    )
    return options


def available_months(rows: list[dict] | None = None) -> list[dict]:
    """Return YYYY-MM buckets, sorted newest first. Each entry has
    {value, label, count, is_current}.

    The current calendar month is ALWAYS included at the top of the list,
    even when it has zero candidates — that way the operator can switch
    to "this month" right after adding a new row without having to
    refresh the page. Same goes for the previous month (helps with
    end-of-month edge cases when working across timezones)."""
    if rows is None:
        rows = list_candidates()
    counts: dict[str, int] = {}
    for r in rows:
        m = _row_display_month(r)
        if m:
            counts[m] = counts.get(m, 0) + 1

    # Ensure current month + last month are present even when empty.
    today = datetime.now(timezone.utc)
    current = today.strftime("%Y-%m")
    counts.setdefault(current, 0)

    prev_year = today.year if today.month > 1 else today.year - 1
    prev_month = today.month - 1 if today.month > 1 else 12
    counts.setdefault(f"{prev_year:04d}-{prev_month:02d}", 0)

    sorted_months = sorted(counts.keys(), reverse=True)
    out = []
    month_names = ("Jan", "Feb", "Mar", "Apr", "May", "Jun",
                   "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")
    for m in sorted_months:
        try:
            year, mo = m.split("-")
            label = f"{month_names[int(mo) - 1]} {year}"
        except (ValueError, IndexError):
            label = m
        out.append({
            "value": m,
            "label": label,
            "count": counts[m],
            "is_current": m == current,
        })
    return out


def _carry_forward_balances(
    target_month: str,
    scope_key: str | None = None,
    service_type_filter: str | None = None,
) -> dict[str, dict]:
    """Compute cumulative commission earned and payouts made for each handler
    across ALL months strictly BEFORE `target_month`.

    Returns {handler_key: {"prior_commission": int, "prior_paid": int}}

    This is READ-ONLY — no writes, no data mutations.
    """
    if not target_month or target_month == "all":
        return {}

    # ── Cumulative commission from prior months ──
    store_data = _load()
    all_rows = [_with_computed(r) for r in (store_data.get("candidates") or [])]
    if scope_key:
        all_rows = [
            r for r in all_rows
            if _reference_key(r.get("reference") or "") == scope_key
        ]
    if service_type_filter and service_type_filter != "all":
        all_rows = [r for r in all_rows if _normalise_service_type(r.get("service_type"), r) == service_type_filter]

    # Only consider candidates from months strictly before target_month
    prior_rows = [r for r in all_rows if _row_display_month(r) and _row_display_month(r) < target_month]
    # Exclude April & May 2026 — those months are treated as fully settled
    prior_rows = [r for r in prior_rows if _row_display_month(r) not in ("2026-04", "2026-05")]
    # Deduplicate using the same logic as stats
    prior_rows = _stats_rows_deduped(prior_rows)

    prior_commission: dict[str, int] = {}
    for r in prior_rows:
        ref_raw = (r.get("reference") or "").strip()
        if not ref_raw:
            continue
        ref_key = _reference_key(ref_raw)
        handler_share = referrer_commission_amount(r)
        prior_commission[ref_key] = prior_commission.get(ref_key, 0) + handler_share

    # ── Cumulative salary from prior months ──
    prior_salary: dict[str, int] = {}
    try:
        from features import handler_salaries as _hs
        # Compute salary for each prior month individually
        # salary_owed_by_handler with month=None returns all-time; we need per-month
        # We'll estimate: if a handler has a monthly salary, multiply by # of prior months
        # Actually safer to call with each prior month, but that's expensive.
        # Instead, gather the distinct prior months and sum salary for each.
        prior_month_set = sorted(set(_row_display_month(r) for r in prior_rows if _row_display_month(r)))
        for pm in prior_month_set:
            if pm >= target_month:
                continue
            # Skip April & May 2026 — treated as settled
            if pm in ("2026-04", "2026-05"):
                continue
            try:
                sal = _hs.salary_owed_by_handler(month=pm)
                for key, sbucket in sal.items():
                    prior_salary[key] = prior_salary.get(key, 0) + int(sbucket.get("owed") or 0)
            except Exception:
                pass
    except Exception:
        pass

    # ── Cumulative payouts from prior months ──
    prior_paid: dict[str, int] = {}
    try:
        from features import handler_expenses as _he
        # Get ALL expenses, then filter to months < target_month
        all_expenses = _he.list_expenses()
        for exp in all_expenses:
            exp_month = (exp.get("date") or "")[:7] if len(exp.get("date") or "") >= 7 else ""
            if not exp_month or exp_month >= target_month:
                continue
            # Skip April & May 2026 — treated as settled
            if exp_month in ("2026-04", "2026-05"):
                continue
            ref = (exp.get("reference") or "").strip()
            if not ref:
                continue
            key = ref.lower()
            if scope_key and key != scope_key:
                continue
            amount = int(exp.get("amount") or 0)
            prior_paid[key] = prior_paid.get(key, 0) + amount
    except Exception:
        pass

    # Merge into result
    all_keys = set(prior_commission.keys()) | set(prior_salary.keys()) | set(prior_paid.keys())
    result: dict[str, dict] = {}
    for key in all_keys:
        comm = prior_commission.get(key, 0)
        sal = prior_salary.get(key, 0)
        paid = prior_paid.get(key, 0)
        # For April & May 2026, prior months are considered settled
        # so don't carry anything forward from those months
        result[key] = {
            "prior_commission": comm,
            "prior_salary": sal,
            "prior_owed": comm + sal,
            "prior_paid": paid,
            "prior_balance": (comm + sal) - paid,
        }
    return result


def stats(
    month: str | None = None,
    reference: str | None = None,
    *,
    service_type: str | None = None,
    _all_rows: list[dict] | None = None,
    _skip_pending_works: bool = False,
) -> dict:
    """Quick KPIs for the dashboard header.

    `month` is either:
      - None / "" / "all" → compute over ALL candidates (no filter)
      - 'YYYY-MM' (e.g. '2025-03') → only count candidates whose `date`
        falls in that calendar month.

    `reference` when set limits every aggregate to one handler/referrer —
    used so referrers never see other people's revenue.

    `service_type` filters by service channel: 'profile_service' or 'round_wise'.
    """
    scope_key: str | None = None
    if reference and str(reference).strip().lower() not in ("", "all"):
        scope_key = _reference_key(str(reference).strip())

    store_data = _load()
    if _all_rows is not None:
        all_rows = _all_rows
    else:
        all_rows = [_with_computed(r) for r in (store_data.get("candidates") or [])]
        if scope_key:
            all_rows = [
                r for r in all_rows
                if _reference_key(r.get("reference") or "") == scope_key
            ]
    # Apply service_type filter before computing stats
    if service_type and service_type != "all":
        all_rows = [r for r in all_rows if _normalise_service_type(r.get("service_type"), r) == service_type]

    if month and month != "all":
        # Use list_candidates (the exact same function the breakdown modal calls)
        # to ensure the stat card revenue matches the breakdown total exactly.
        rows = list_candidates(month=month, reference=reference, service_type=service_type)
    else:
        rows = _stats_rows_deduped(all_rows)

    total = len(rows)
    by_stage = {s: 0 for s in VALID_STAGES}
    revenue = 0
    revenue_by_tech: dict[str, int] = {}
    company_by_tech: dict[str, int] = {}
    company_revenue = 0
    company_revenue_completed = 0
    referral_commission = 0
    completed_revenue = 0
    expected_total = 0
    pending_total = 0
    pending_count = 0
    pending_no_remark = 0  # rows that still owe money AND have no follow-up note yet
    consultancy_count   = 0
    consultancy_revenue = 0
    direct_count        = 0
    direct_revenue      = 0

    perf: dict[str, dict] = {}
    _service_type_param = service_type  # preserve original param before loop overwrites it
    for r in rows:
        st = r.get("stage") or "in_progress"
        by_stage[st] = by_stage.get(st, 0) + 1
        amt = int(r.get("payment") or 0)
        is_consultancy = bool(r.get("consultancy"))
        service_type = _normalise_service_type(r.get("service_type"), r)
        interview_scope = _normalise_interview_scope(r.get("interview_scope"), r)
        expected = effective_expected_payment(r)
        balance = max(0, expected - amt)
        # Handler commission follows the agreed deal (expected_payment), not
        # the prescribed baseline — partial payments accrue gradually.
        handler_share = referrer_commission_amount(r)
        company_share = max(0, amt - handler_share)
        revenue += amt
        referral_commission += handler_share
        company_revenue += company_share
        expected_total += expected
        if is_consultancy:
            consultancy_count   += 1
            consultancy_revenue += amt
        else:
            direct_count   += 1
            direct_revenue += amt
        tech = (r.get("technology") or "Unspecified").strip() or "Unspecified"
        revenue_by_tech[tech] = revenue_by_tech.get(tech, 0) + amt
        company_by_tech[tech] = company_by_tech.get(tech, 0) + company_share
        if st == "completed":
            completed_revenue += amt
            company_revenue_completed += company_share

        ref_raw = (r.get("reference") or "Unknown").strip() or "Unknown"
        ref_key = _reference_key(ref_raw)
        bucket = perf.get(ref_key)
        if bucket is None:
            bucket = {
                "ref_key": ref_key,
                "name": _canonical_reference_name(ref_raw) if ref_raw != "Unknown" else "Unknown",
                "count": 0, "completed": 0, "in_progress": 0,
                "fail": 0, "dropped": 0, "revenue_total": 0, "revenue_completed": 0,
                "pending_total": 0, "pending_count": 0,
                "auto_earnings_total": 0, "auto_earnings_completed": 0,
                "company_revenue_total": 0, "company_revenue_completed": 0,
                "consultancy_count": 0,
            }
            perf[ref_key] = bucket
        else:
            bucket["name"] = _prefer_reference_display(bucket["name"], ref_raw)
        bucket["count"] += 1
        if st in bucket:
            bucket[st] += 1
        bucket["revenue_total"] += amt
        bucket["company_revenue_total"] += company_share
        bucket["auto_earnings_total"] += handler_share
        if is_consultancy:
            bucket["consultancy_count"] += 1
        if st == "completed":
            bucket["revenue_completed"] += amt
            bucket["company_revenue_completed"] += company_share
            bucket["auto_earnings_completed"] += handler_share

    pending_total, pending_count, pending_no_remark, pending_by_ref = (
        _pending_collections_from_rows(rows)
    )
    for ref_key, pb in pending_by_ref.items():
        bucket = perf.get(ref_key)
        if bucket is not None:
            bucket["pending_total"] = pb["pending_total"]
            bucket["pending_count"] = pb["pending_count"]

    # Join in the handler_expenses ledger — which now represents money the
    # operator has ALREADY PAID OUT (commission disbursements, travel,
    # food, etc.). The handler's earnings are auto-computed above from the
    # 50% rule, so the ledger is no longer split into "earning vs
    # deduction" — every row is a payout against what they're owed.
    try:
        from features import handler_expenses as _he
        expense_summary = _he.summary_by_handler(
            month=month if month and month != "all" else None,
        )
    except Exception:
        expense_summary = {}
    if scope_key:
        expense_summary = {
            k: v for k, v in expense_summary.items()
            if k == scope_key or _reference_matches_scope(v.get("name") or k, scope_key)
        }

    # Join in the per-handler salary store. A handler can be on a hybrid
    # pay model: a fixed monthly salary (this) PLUS 50% commission on
    # their candidates' payments (computed above). Handlers with a
    # salary but no candidates this period still need to appear in
    # top_performers — we add a bucket for them below.
    try:
        from features import handler_salaries as _hs
        salary_summary = _hs.salary_owed_by_handler(
            month=month if month and month != "all" else None,
        )
    except Exception:
        salary_summary = {}
    if scope_key:
        salary_summary = {
            k: v for k, v in salary_summary.items()
            if k == scope_key or _reference_matches_scope(v.get("name") or k, scope_key)
        }

    # Make sure every salaried handler has a perf bucket, even those who
    # didn't refer anyone this period (otherwise their salary obligation
    # would silently disappear from the Top Performers panel).
    for key, sbucket in salary_summary.items():
        ref = sbucket.get("name") or key
        if _payout_excluded_handler(ref):
            continue
        if not _reference_matches_scope(ref, scope_key):
            continue
        ref_key = _reference_key(ref)
        if ref_key not in perf:
            perf[ref_key] = {
                "ref_key": ref_key,
                "name": _canonical_reference_name(ref) or ref,
                "count": 0, "completed": 0, "in_progress": 0,
                "fail": 0, "dropped": 0, "revenue_total": 0, "revenue_completed": 0,
                "pending_total": 0, "pending_count": 0,
                "auto_earnings_total": 0, "auto_earnings_completed": 0,
                "company_revenue_total": 0, "company_revenue_completed": 0,
                "consultancy_count": 0,
            }
        else:
            perf[ref_key]["name"] = _prefer_reference_display(perf[ref_key]["name"], ref)

    total_handler_commission    = 0
    total_handler_salary        = 0
    total_handler_paid_out      = 0

    # ── Carry-forward: compute cumulative balances from prior months ──
    carry_fwd: dict[str, dict] = {}
    if month and month != "all":
        carry_fwd = _carry_forward_balances(
            target_month=month,
            scope_key=scope_key,
            service_type_filter=_service_type_param if _service_type_param and _service_type_param != "all" else None,
        )
        # Make sure every handler with a non-zero carry-forward balance
        # has a perf bucket, even those with no candidates this month.
        for key, cf_data in carry_fwd.items():
            prior_bal = int(cf_data.get("prior_balance") or 0)
            if prior_bal == 0:
                continue
            if _payout_excluded_handler(key):
                continue
            ref_key = key  # already lowercased
            if ref_key not in perf:
                perf[ref_key] = {
                    "ref_key": ref_key,
                    "name": _canonical_reference_name(key) or key.title(),
                    "count": 0, "completed": 0, "in_progress": 0,
                    "fail": 0, "dropped": 0, "revenue_total": 0, "revenue_completed": 0,
                    "pending_total": 0, "pending_count": 0,
                    "auto_earnings_total": 0, "auto_earnings_completed": 0,
                    "company_revenue_total": 0, "company_revenue_completed": 0,
                    "consultancy_count": 0,
                }

    for p in perf.values():
        p["conversion_pct"] = (
            round((p["completed"] / p["count"]) * 100) if p["count"] else 0
        )
        key = (p.get("ref_key") or _reference_key(p.get("name"))).strip().lower()
        exp_bucket    = expense_summary.get(key, {})
        salary_bucket = salary_summary.get(key, {})

        commission = int(p["auto_earnings_total"])
        salary     = int(salary_bucket.get("owed") or 0)
        owed       = commission + salary
        paid_out   = int(exp_bucket.get("total") or 0)

        # ── Carry-forward: only the NET BALANCE from prior months ──
        cf = carry_fwd.get(key, {})
        prior_balance = int(cf.get("prior_balance") or 0)

        # Salary-side fields — show THIS month's values only.
        p["commission_total"]  = commission
        p["salary_total"]      = salary
        p["salary_monthly"]    = int(salary_bucket.get("monthly_salary") or 0)
        p["salary_active"]     = bool(salary_bucket.get("monthly_salary"))

        # Owed = commission + salary (THIS month only).
        p["auto_earnings_total"] = owed

        # Paid out = THIS month's payouts only.
        p["paid_out_total"]    = paid_out
        p["paid_out_count"]    = int(exp_bucket.get("count") or 0)

        # Balance = this month's (owed - paid) + carry-forward from prior months.
        p["net_payable"]       = (owed - paid_out) + prior_balance
        p["commission_pct"]    = HANDLER_COMMISSION_PCT

        # Carry-forward detail field so UI can show the breakdown.
        p["prior_balance"]     = prior_balance

        # ── April & May 2026: treat as fully settled for all handlers ──
        if month in ("2026-04", "2026-05"):
            p["net_payable"] = 0
            p["prior_balance"] = 0

        # Backwards-compat aliases so older client bundles keep rendering
        # something sensible until the next refresh:
        p["earnings_total"]    = owed
        p["deductions_total"]  = paid_out
        p["net_earning"]       = (owed - paid_out) + prior_balance
        p["expenses_total"]    = paid_out
        p["expenses_count"]    = int(exp_bucket.get("count") or 0)
        p["net_completed"]     = int(p.get("revenue_completed") or 0) - paid_out

        if _payout_excluded_handler(key) or _payout_excluded_handler(p.get("name") or ""):
            p["payout_excluded"] = True
            p["commission_total"] = 0
            p["salary_total"] = 0
            p["salary_monthly"] = 0
            p["salary_active"] = False
            p["auto_earnings_total"] = 0
            p["paid_out_total"] = 0
            p["paid_out_count"] = 0
            p["net_payable"] = 0
            p["prior_balance"] = 0
            p["earnings_total"] = 0
            p["deductions_total"] = 0
            p["net_earning"] = 0
            p["expenses_total"] = 0
            p["expenses_count"] = 0
            continue

        total_handler_commission += commission
        total_handler_salary     += salary
        total_handler_paid_out   += paid_out

    total_handler_auto_earnings = total_handler_commission + total_handler_salary
    # Sum of all handlers' prior balances for the global net payout
    total_prior_balance = sum(int(p.get("prior_balance") or 0) for p in perf.values() if not p.get("payout_excluded"))

    # ── April & May 2026: force global handler payout to settled ──
    if month in ("2026-04", "2026-05"):
        total_handler_auto_earnings = total_handler_paid_out

    top_tech = sorted(company_by_tech.items(), key=lambda kv: kv[1], reverse=True)[:5]
    top_performers = sorted(
        perf.values(),
        key=lambda b: (b["revenue_completed"], b["revenue_total"], b["count"]),
        reverse=True,
    )
    if scope_key:
        top_performers = [
            p for p in top_performers
            if (p.get("ref_key") or _reference_key(p.get("name") or "")) == scope_key
        ]

    result = {
        "total": total,
        "by_stage": by_stage,
        "revenue_total": revenue,
        "revenue_completed": completed_revenue,
        # Company revenue = client cash in minus referrer commission only.
        "client_collections_total": revenue,
        "referral_commission_total": referral_commission,
        "company_revenue_total": company_revenue,
        "company_revenue_completed": company_revenue_completed,
        "expected_total": expected_total,
        "pending_total": pending_total,
        "pending_count": pending_count,
        "pending_no_remark": pending_no_remark,
        "default_expected_payment":           DEFAULT_EXPECTED_PAYMENT,
        "consultancy_expected_payment":       CONSULTANCY_EXPECTED_PAYMENT,
        # Channel split — direct (₹20k baseline) vs consultancy (₹15k baseline)
        "consultancy_count":   consultancy_count,
        "consultancy_revenue": consultancy_revenue,
        "direct_count":        direct_count,
        "direct_revenue":      direct_revenue,
        # Handler-payout view (new model):
        #   owed  = sum of auto-computed 50% commissions
        #   paid  = sum of every handler_expenses ledger row
        #   net   = owed − paid (positive = operator still owes the handler)
        "commission_pct":               HANDLER_COMMISSION_PCT,
        "handler_auto_earnings_total":  total_handler_auto_earnings,
        "handler_commission_total":     total_handler_commission,
        "handler_salary_total":         total_handler_salary,
        "handler_paid_out_total":       total_handler_paid_out,
        "net_handler_payout":           (total_handler_auto_earnings - total_handler_paid_out) + total_prior_balance,
        # Backwards-compat fields (older client builds expect these names).
        "handler_earnings_total":   total_handler_auto_earnings,
        "handler_deductions_total": total_handler_paid_out,
        "handler_expenses_total":   total_handler_paid_out,
        "net_completed":            completed_revenue - total_handler_paid_out,
        "month": month or "all",
        # Distinct months across ALL rows (so the picker doesn't change as
        # the user navigates between months).
        "available_months": available_months(all_rows),
        "top_technologies": [{"name": k, "revenue": v} for k, v in top_tech],
        "top_technologies_gross": [
            {"name": k, "revenue": v}
            for k, v in sorted(revenue_by_tech.items(), key=lambda kv: kv[1], reverse=True)[:5]
        ],
        # Kept for backwards-compat with anything still consuming the old
        # by-count list; new UI uses `top_performers`.
        "top_references": [
            {"name": p["name"], "count": p["count"]}
            for p in sorted(perf.values(), key=lambda b: b["count"], reverse=True)[:5]
        ],
        "top_performers": top_performers,
        # Build selector counts from the same final, merged records returned
        # by /candidates.  Raw stats rows can retain an old referrer on a
        # duplicate profile, which makes a badge disagree with the table.
        "handler_references": _handler_reference_options(
            list_candidates(month=month),
            month=None,
            scope_key=scope_key,
        ),
        "updated_at": store_data.get("updated_at"),
    }
    if _skip_pending_works:
        return result
    _pw = pending_works(reference=reference)
    return _attach_pending_work_stats(result, _pw)


def bootstrap_data(
    *,
    stage: str | None = None,
    task: str | None = None,
    search: str | None = None,
    month: str | None = None,
    pending_only: bool = False,
    reference: str | None = None,
    include_global_stats: bool = False,
) -> dict:
    """Single-pass list + stats for the Candidates page (one DB read, one enrich pass)."""
    scope_key: str | None = None
    if reference and str(reference).strip().lower() not in ("", "all"):
        scope_key = _reference_key(str(reference).strip())

    store_data = _load()
    all_rows = [_with_computed(r) for r in (store_data.get("candidates") or [])]
    scoped_rows = all_rows
    if scope_key:
        scoped_rows = [
            r for r in all_rows
            if _reference_key(r.get("reference") or "") == scope_key
        ]

    list_rows = _apply_list_filters(
        scoped_rows,
        stage=stage,
        task=task,
        search=search,
        month=month,
        pending_only=pending_only,
        reference=reference,
    )
    stats_payload = stats(
        month=month,
        reference=reference,
        _all_rows=scoped_rows,
        _skip_pending_works=True,
    )
    pw = _pending_works_core(_in_progress_rows(scoped_rows, None))
    stats_payload = _attach_pending_work_stats(stats_payload, pw)

    payload: dict = {
        "candidates": [_slim_list_row(r) for r in list_rows],
        "count": len(list_rows),
        "stats": stats_payload,
    }
    if include_global_stats:
        global_stats = stats(
            month=month,
            reference=None,
            _all_rows=all_rows,
            _skip_pending_works=True,
        )
        pw_global = _pending_works_core(_in_progress_rows(all_rows, None))
        payload["global_stats"] = _attach_pending_work_stats(global_stats, pw_global)
    return payload


# ── Payment-proof helpers ───────────────────────────────────────────────────

def _proof_dir(cid: str) -> str:
    return os.path.join(PROOFS_DIR, cid)


def _ext_from_mime(mime: str, fallback_name: str = "") -> str:
    mime = (mime or "").lower().split(";")[0].strip()
    if mime in _ALLOWED_MIME:
        return _ALLOWED_MIME[mime]
    # Last-resort guess from the filename extension.
    if fallback_name and "." in fallback_name:
        ext = fallback_name.rsplit(".", 1)[-1].lower()
        if ext in {"jpg", "jpeg", "png", "webp", "gif", "heic", "heif"}:
            return "jpeg" if ext == "jpeg" else ext
    return ""


def add_proof(cid: str, *, data: bytes, original_name: str, mime_type: str,
              note: str = "") -> dict | None:
    """Persist a payment screenshot for `cid`. Returns the new proof entry
    (with its computed url path) or None when the candidate doesn't exist
    or the upload is rejected (wrong mime, too big, empty)."""
    if not data:
        raise ValueError("Empty upload")
    if len(data) > MAX_PROOF_BYTES:
        raise ValueError(f"File too large (max {MAX_PROOF_BYTES // (1024*1024)} MB)")
    ext = _ext_from_mime(mime_type, original_name)
    if not ext:
        raise ValueError("Only image files (jpg / png / webp / gif / heic) are allowed")

    cdata = _load()
    rows = cdata.get("candidates") or []
    idx = next((i for i, r in enumerate(rows) if r.get("id") == cid), -1)
    if idx < 0:
        return None

    pid = uuid.uuid4().hex[:12]
    filename = f"{pid}.{ext}"
    folder = _proof_dir(cid)
    os.makedirs(folder, exist_ok=True)
    path = os.path.join(folder, filename)
    # Write atomically so we never serve a half-flushed screenshot.
    tmp = path + ".tmp"
    with open(tmp, "wb") as f:
        f.write(data)
    os.replace(tmp, path)

    entry = {
        "id":            pid,
        "filename":      filename,
        "original_name": (original_name or filename)[:160],
        "mime_type":     mime_type or f"image/{ext}",
        "size":          len(data),
        "note":          _clean_str(note)[:200],
        "uploaded_at":   _now_iso(),
        "url":           f"/candidates/{cid}/proofs/{pid}",
    }
    proofs = list(rows[idx].get("proofs") or [])
    proofs.append(entry)
    rows[idx]["proofs"] = proofs
    rows[idx]["updated_at"] = _now_iso()
    cdata["candidates"] = rows
    _save(cdata)
    return entry


def list_proofs(cid: str) -> list[dict] | None:
    """Return the persisted proof list for `cid` or None if missing."""
    for r in _load().get("candidates") or []:
        if r.get("id") == cid:
            return list(r.get("proofs") or [])
    return None


def get_proof(cid: str, pid: str) -> tuple[str, dict] | None:
    """Locate the proof's on-disk path + metadata for serving. Returns
    (absolute_path, entry) or None when either id doesn't resolve."""
    for r in _load().get("candidates") or []:
        if r.get("id") != cid:
            continue
        for p in (r.get("proofs") or []):
            if p.get("id") == pid:
                path = os.path.join(_proof_dir(cid), p["filename"])
                if not os.path.exists(path):
                    return None
                return path, dict(p)
        return None
    return None


def delete_proof(cid: str, pid: str) -> bool:
    """Remove a proof from the candidate + delete its file from disk.
    Also searches slot-clone rows with the same name in case proof was merged from another row."""
    cdata = _load()
    rows = cdata.get("candidates") or []
    # First try the exact row
    target_row = next((r for r in rows if r.get("id") == cid), None)
    if target_row:
        proofs = list(target_row.get("proofs") or [])
        for i, p in enumerate(proofs):
            if p.get("id") == pid:
                path = os.path.join(_proof_dir(cid), p["filename"])
                try:
                    if os.path.exists(path):
                        os.remove(path)
                except OSError:
                    pass
                proofs.pop(i)
                target_row["proofs"] = proofs
                target_row["updated_at"] = _now_iso()
                cdata["candidates"] = rows
                _save(cdata)
                return True
    # If not found on the target row, search all rows with the same name (slot clones)
    if target_row:
        name_key = _normalise_candidate_name_key(target_row.get("name") or "")
        for r in rows:
            if r.get("id") == cid:
                continue
            if _normalise_candidate_name_key(r.get("name") or "") != name_key:
                continue
            proofs = list(r.get("proofs") or [])
            for i, p in enumerate(proofs):
                if p.get("id") == pid:
                    path = os.path.join(_proof_dir(r["id"]), p["filename"])
                    try:
                        if os.path.exists(path):
                            os.remove(path)
                    except OSError:
                        pass
                    proofs.pop(i)
                    r["proofs"] = proofs
                    r["updated_at"] = _now_iso()
                    cdata["candidates"] = rows
                    _save(cdata)
                    return True
    return False


def update_proof_note(cid: str, pid: str, note: str) -> dict | None:
    """Operator can tag a proof after upload (e.g. '₹10k UPI · 26 May')."""
    cdata = _load()
    rows = cdata.get("candidates") or []
    for r in rows:
        if r.get("id") != cid:
            continue
        for p in (r.get("proofs") or []):
            if p.get("id") == pid:
                p["note"] = _clean_str(note)[:200]
                r["updated_at"] = _now_iso()
                cdata["candidates"] = rows
                _save(cdata)
                return dict(p)
        return None
    return None


# ── Resume helpers ────────────────────────────────────────────────────────────

def _resume_dir(cid: str) -> str:
    return os.path.join(RESUMES_DIR, cid)


def reconcile_resume_metadata() -> int:
    """Restore metadata for resume files that survived an incomplete restore.

    Earlier deployments preserved the documents in ``candidates_resumes`` but
    dropped their JSON records.  Recreate a minimal version record only when a
    folder belongs to an existing candidate; unknown folders are left untouched
    rather than risk assigning a document to the wrong person.
    """
    if not os.path.isdir(RESUMES_DIR):
        return 0
    data = _load()
    changed = 0
    for row in data.get("candidates") or []:
        cid = _clean_str(row.get("id"))
        if not cid:
            continue
        folder = _resume_dir(cid)
        if not os.path.isdir(folder):
            continue
        entries = list(row.get("resumes") or [])
        known = {_clean_str(item.get("filename")) for item in entries}
        row_changed = False
        for filename in sorted(os.listdir(folder)):
            path = os.path.join(folder, filename)
            if not os.path.isfile(path) or filename in known:
                continue
            ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
            mime = {
                "pdf": "application/pdf",
                "doc": "application/msword",
                "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                "txt": "text/plain",
            }.get(ext)
            if not mime:
                continue
            entries.append({
                "id": filename.rsplit(".", 1)[0][:32],
                "filename": filename,
                "original_name": filename,
                "mime_type": mime,
                "size": os.path.getsize(path),
                "note": "",
                "uploaded_at": datetime.fromtimestamp(
                    os.path.getmtime(path), timezone.utc
                ).isoformat(),
                "url": f"/candidates/{cid}/resumes/{filename.rsplit('.', 1)[0][:32]}",
            })
            known.add(filename)
            changed += 1
            row_changed = True
        if row_changed:
            row["resumes"] = entries
    if changed:
        _save(data)
    return changed


def _resume_storage_candidate_id(candidate_id: str, entry: dict) -> str:
    """Find the folder that actually owns a stored resume file.

    Profile de-duplication can give a candidate a new visible ID while their
    older resume record keeps its original URL.  Keep that legacy folder link
    intact so existing files remain viewable instead of looking "missing".
    """
    stored = _clean_str(entry.get("storage_candidate_id"))
    if stored:
        return stored
    match = re.search(r"/candidates/([^/]+)/resumes/", _clean_str(entry.get("url")))
    return match.group(1) if match else candidate_id


def _ext_from_resume_mime(mime: str, fallback_name: str = "") -> str:
    mime = (mime or "").lower().split(";")[0].strip()
    if mime in _ALLOWED_RESUME_MIME:
        return _ALLOWED_RESUME_MIME[mime]
    if fallback_name and "." in fallback_name:
        ext = fallback_name.rsplit(".", 1)[-1].lower()
        if ext in {"pdf", "doc", "docx", "txt"}:
            return ext
    return ""


def add_resume(cid: str, *, data: bytes, original_name: str, mime_type: str,
               note: str = "") -> dict | None:
    """Persist an updated resume for `cid`. Each upload is kept as a version."""
    if not data:
        raise ValueError("Empty upload")
    if len(data) > MAX_RESUME_BYTES:
        raise ValueError(f"File too large (max {MAX_RESUME_BYTES // (1024*1024)} MB)")
    ext = _ext_from_resume_mime(mime_type, original_name)
    if not ext:
        raise ValueError("Only PDF, Word (.doc/.docx), or plain text files are allowed")

    cdata = _load()
    rows = cdata.get("candidates") or []
    idx = next((i for i, r in enumerate(rows) if r.get("id") == cid), -1)
    if idx < 0:
        return None

    rid = uuid.uuid4().hex[:12]
    filename = f"{rid}.{ext}"
    folder = _resume_dir(cid)
    os.makedirs(folder, exist_ok=True)
    path = os.path.join(folder, filename)
    tmp = path + ".tmp"
    with open(tmp, "wb") as f:
        f.write(data)
    os.replace(tmp, path)

    entry = {
        "id":            rid,
        "filename":      filename,
        "original_name": (original_name or filename)[:160],
        "mime_type":     mime_type or "application/octet-stream",
        "size":          len(data),
        "note":          _clean_str(note)[:200],
        "uploaded_at":   _now_iso(),
        "url":           f"/candidates/{cid}/resumes/{rid}",
    }
    resumes = list(rows[idx].get("resumes") or [])
    resumes.append(entry)
    rows[idx]["resumes"] = resumes
    rows[idx]["updated_at"] = _now_iso()
    cdata["candidates"] = rows
    _save(cdata)
    return entry


def get_resume(cid: str, rid: str) -> tuple[str, dict] | None:
    for r in _load().get("candidates") or []:
        if r.get("id") != cid:
            continue
        for item in (r.get("resumes") or []):
            if item.get("id") == rid:
                storage_cid = _resume_storage_candidate_id(cid, item)
                path = os.path.join(_resume_dir(storage_cid), item["filename"])
                if not os.path.exists(path):
                    return None
                return path, dict(item)
        return None
    return None


def delete_resume(cid: str, rid: str) -> bool:
    cdata = _load()
    rows = cdata.get("candidates") or []
    for r in rows:
        if r.get("id") != cid:
            continue
        resumes = list(r.get("resumes") or [])
        for i, item in enumerate(resumes):
            if item.get("id") == rid:
                storage_cid = _resume_storage_candidate_id(cid, item)
                path = os.path.join(_resume_dir(storage_cid), item["filename"])
                try:
                    if os.path.exists(path):
                        os.remove(path)
                except OSError:
                    pass
                resumes.pop(i)
                r["resumes"] = resumes
                r["updated_at"] = _now_iso()
                cdata["candidates"] = rows
                _save(cdata)
                return True
        return False
    return False


def update_resume_note(cid: str, rid: str, note: str) -> dict | None:
    cdata = _load()
    rows = cdata.get("candidates") or []
    for r in rows:
        if r.get("id") != cid:
            continue
        for item in (r.get("resumes") or []):
            if item.get("id") == rid:
                item["note"] = _clean_str(note)[:200]
                r["updated_at"] = _now_iso()
                cdata["candidates"] = rows
                _save(cdata)
                return dict(item)
        return None
    return None


def bulk_replace(rows: list[dict]) -> int:
    """Replace the entire list (used by the one-shot seed importer).
    Returns the count written."""
    cleaned = [_normalise(r) for r in rows if (r.get("name") or "").strip()]
    _save({"candidates": cleaned, "updated_at": _now_iso()})
    return len(cleaned)


def bulk_upsert(rows: list[dict]) -> dict:
    """Append rows, dedup by (name, phone, date) to avoid double-imports.
    Returns counts of added / skipped."""
    data = _load()
    existing = data.get("candidates") or []
    existing_keys = {
        ((r.get("name") or "").lower(), (r.get("phone") or ""), (r.get("date") or ""))
        for r in existing
    }
    added = 0
    skipped = 0
    for raw in rows:
        if not (raw.get("name") or "").strip():
            skipped += 1
            continue
        row = _normalise(raw)
        key = (row["name"].lower(), row["phone"], row["date"])
        if key in existing_keys:
            skipped += 1
            continue
        existing.append(row)
        existing_keys.add(key)
        added += 1
    data["candidates"] = existing
    _save(data)
    return {"added": added, "skipped": skipped, "total": len(existing)}
