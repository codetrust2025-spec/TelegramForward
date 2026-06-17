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
        "date":          "YYYY-MM-DD" (date the deal was logged, blank ok),
        "time":          "HH:MM" 24h (blank ok),
        "slot_confirmed": false until owner + initial payment (handler workspace rule),
        "slot_confirmed_at": ISO timestamp when slot was confirmed (blank ok),
        "slots_group_posted": true after slot screenshot posted in Interview slots WA group,
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
import time
import uuid
from datetime import datetime, timezone
from threading import Lock

from core.config import DATA_DIR

_FILE = os.path.join(DATA_DIR, "candidates.json")
# Each candidate gets its own folder under here so we never accidentally
# mix screenshots between people, even if filenames collide.
PROOFS_DIR = os.path.join(DATA_DIR, "candidates_proofs")
_lock = Lock()

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
MAX_PROOF_BYTES = 8 * 1024 * 1024  # 8 MB per screenshot

VALID_STAGES = {"in_progress", "completed", "fail", "dropped"}
VALID_TASKS = {"not_started", "in_progress", "decision_need", "completed"}

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
ROUND_WISE_DOMESTIC_PAYMENT    = 5_000
ROUND_WISE_NON_DOMESTIC_PAYMENT = 9_000
# Minimum initial payment before a handler may mark the interview slot confirmed.
PROFILE_SERVICE_SLOT_MIN_PAYMENT = 10_000

VALID_SERVICE_TYPES = {"profile_service", "round_wise"}
VALID_INTERVIEW_SCOPES = {"domestic", "non_domestic"}
VALID_PURPOSES = {"interview_support", "work_support", "experience_docs", "other"}


def baseline_for(consultancy: bool) -> int:
    """The default rupee baseline a candidate is expected to pay."""
    return CONSULTANCY_EXPECTED_PAYMENT if consultancy else DEFAULT_EXPECTED_PAYMENT


def baseline_for_service(
    service_type: str,
    *,
    consultancy: bool = False,
    interview_scope: str = "domestic",
) -> int:
    if service_type == "round_wise":
        return (
            ROUND_WISE_NON_DOMESTIC_PAYMENT
            if interview_scope == "non_domestic"
            else ROUND_WISE_DOMESTIC_PAYMENT
        )
    return baseline_for(consultancy)

# The referrer (handler) is paid this share of every rupee the client pays
# the business. The operator does not log commissions by hand — they're
# computed from the candidate's `payment` field. The handler_expenses
# ledger now only tracks money already paid OUT (commission disbursements,
# travel, food etc.) — net = auto_earnings − paid_out.
HANDLER_COMMISSION_PCT = 50


# ── Helpers ─────────────────────────────────────────────────────────────────

def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _new_id() -> str:
    return uuid.uuid4().hex[:10]


def _empty() -> dict:
    return {"candidates": [], "updated_at": None}


def _load() -> dict:
    from core.db.connection import use_postgres

    if use_postgres():
        from core.db.candidates_pg import pg_load as pg_candidates_load
        data = pg_candidates_load()
        if not data.get("candidates"):
            return _empty()
        data.setdefault("updated_at", None)
        return data
    with _lock:
        if not os.path.exists(_FILE):
            return _empty()
        try:
            with open(_FILE, encoding="utf-8") as f:
                data = json.load(f)
            if not isinstance(data, dict):
                return _empty()
            data.setdefault("candidates", [])
            data.setdefault("updated_at", None)
            return data
        except (OSError, json.JSONDecodeError):
            return _empty()


def _save(data: dict) -> None:
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
    "payment", "expected_payment", "follow_up",
    "date", "time", "expenses", "notes",
    "telegram_slot", "telegram_user_id",
    "service_type", "interview_scope",
    "slot_confirmed",
    "slots_group_posted",
    "purpose",
}


def minimum_payment_for_slot(row: dict) -> int:
    """Rupee threshold before slot_confirmed is allowed (owner + money rule)."""
    service_type = _normalise_service_type(row.get("service_type"), row)
    interview_scope = _normalise_interview_scope(row.get("interview_scope"), row)
    consultancy = bool(row.get("consultancy", False))
    if service_type == "round_wise":
        return baseline_for_service(
            service_type,
            consultancy=consultancy,
            interview_scope=interview_scope,
        )
    expected = int(row.get("expected_payment") or 0)
    if expected <= 0:
        expected = baseline_for_service(
            service_type,
            consultancy=consultancy,
            interview_scope=interview_scope,
        )
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
    val = _clean_str(raw if raw is not None else (base or {}).get("interview_scope", "domestic")).lower()
    if val in ("non-domestic", "non domestic", "international", "abroad", "usa", "us"):
        return "non_domestic"
    return val if val in VALID_INTERVIEW_SCOPES else "domestic"


def _normalise(record: dict, *, existing: dict | None = None) -> dict:
    """Turn whatever the UI sent into a clean row, preserving existing
    timestamps when patching."""
    base = dict(existing) if existing else {}

    # `consultancy` flips the default baseline: True → ₹15k, False → ₹20k.
    # Stored as a clean bool so the UI doesn't have to guess from strings.
    consultancy = _coerce_bool(record.get("consultancy", base.get("consultancy", False)))
    service_type = _normalise_service_type(record.get("service_type"), base)
    interview_scope = _normalise_interview_scope(record.get("interview_scope"), base)
    if service_type == "round_wise":
        consultancy = False

    default_for_channel = baseline_for_service(
        service_type,
        consultancy=consultancy,
        interview_scope=interview_scope,
    )
    exp_raw = record.get("expected_payment",
                         base.get("expected_payment", default_for_channel))
    expected = _coerce_payment(exp_raw)
    if expected <= 0:
        expected = default_for_channel

    # `proofs` is intentionally NOT in _ALLOWED_FIELDS — it's only mutated
    # through add_proof / delete_proof so screenshots can't be wiped by a
    # plain PATCH on the candidate record.
    out = {
        "id":               base.get("id") or _new_id(),
        "name":             _clean_str(record.get("name", base.get("name"))),
        "stage":            _clean_str(record.get("stage", base.get("stage", "in_progress"))).lower().replace(" ", "_"),
        "technology":       _clean_str(record.get("technology", base.get("technology"))),
        "task":             _clean_str(record.get("task", base.get("task", "not_started"))).lower().replace(" ", "_"),
        "phone":            _clean_str(record.get("phone", base.get("phone"))),
        "reference":        _canonical_reference_name(
            _clean_str(record.get("reference", base.get("reference")))
        ),
        "consultancy":      consultancy,
        "service_type":     service_type,
        "interview_scope":  interview_scope if service_type == "round_wise" else "",
        "payment":          _coerce_payment(record.get("payment", base.get("payment"))),
        "expected_payment": expected,
        "follow_up":        _clean_str(record.get("follow_up", base.get("follow_up"))),
        "purpose":          _normalise_purpose(record.get("purpose"), base),
        "date":             _clean_str(record.get("date", base.get("date"))),
        "time":             _clean_str(record.get("time", base.get("time"))),
        "expenses":         _clean_str(record.get("expenses", base.get("expenses"))),
        "notes":            _clean_str(record.get("notes", base.get("notes"))),
        "telegram_slot":    _clean_str(record.get("telegram_slot", base.get("telegram_slot"))),
        "telegram_user_id": int(record.get("telegram_user_id") or base.get("telegram_user_id") or 0) or None,
        "proofs":           list(base.get("proofs") or []),
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
    if out["stage"] not in VALID_STAGES:
        out["stage"] = "in_progress"
    if out["task"] not in VALID_TASKS:
        out["task"] = "not_started"
    return out


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
    )
    expected = int(row.get("expected_payment") or fallback)
    if expected <= 0:
        expected = fallback
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
    enriched["service_type"] = service_type
    enriched["interview_scope"] = interview_scope if service_type == "round_wise" else ""
    enriched["expected_payment"] = expected
    enriched["balance_due"] = balance
    enriched["payment_status"] = status
    enriched["needs_followup"] = balance > 0
    proofs = enriched.get("proofs") or []
    enriched["proofs"] = proofs
    enriched["proof_count"] = len(proofs)
    slot_ok = can_confirm_slot(enriched)
    enriched["can_confirm_slot"] = slot_ok
    enriched["slot_confirm_block_reason"] = slot_confirm_block_reason(enriched)
    enriched["slot_confirm_min_payment"] = minimum_payment_for_slot(enriched)
    return enriched


# ── Public API ──────────────────────────────────────────────────────────────

def list_candidates(*, stage: str | None = None, task: str | None = None,
                    search: str | None = None, month: str | None = None,
                    pending_only: bool = False,
                    reference: str | None = None) -> list[dict]:
    """Return candidates sorted by most-recent first.
    Optional filters: by stage, by task, by free-text search across
    name / technology / reference / phone / notes / follow_up, by month
    ('YYYY-MM'), `pending_only=True` to keep only rows where the
    received payment is less than the expected baseline, and `reference`
    for an exact case-insensitive handler match (so the dashboard can
    show only one handler's leads)."""
    data = _load()
    rows = [_with_computed(r) for r in (data.get("candidates") or [])]
    if stage and stage != "all":
        rows = [r for r in rows if r.get("stage") == stage]
    if task and task != "all":
        rows = [r for r in rows if r.get("task") == task]
    if month and month != "all":
        rows = [r for r in rows if _row_month(r) == month]
    if pending_only:
        rows = [r for r in rows if r.get("balance_due", 0) > 0]
    if reference and reference != "all":
        # Exact handler match, normalised: lowercase + stripped so
        # "Thrilok " and "thrilok" both match the dropdown selection.
        needle = reference.strip().lower()
        rows = [r for r in rows if (r.get("reference") or "").strip().lower() == needle]
    if search:
        q = search.strip().lower()
        if q:
            def _hit(r: dict) -> bool:
                # Typing "consultancy" in search filters to consultancy leads
                # since the flag is rendered as a tag/badge in the UI.
                if q == "consultancy" and r.get("consultancy"):
                    return True
                for k in ("name", "technology", "reference", "phone", "notes", "follow_up"):
                    if q in (r.get(k) or "").lower():
                        return True
                return False
            rows = [r for r in rows if _hit(r)]
    rows.sort(key=lambda r: (r.get("date") or "", r.get("updated_at") or ""), reverse=True)
    return rows


def get_candidate(cid: str) -> dict | None:
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
    """Extract a 'YYYY-MM' bucket from a row's date. Empty string if the
    date is missing or unparseable — those rows go into the 'undated' bin
    and only show up when month filter is 'all'."""
    raw = (row.get("date") or "").strip()
    if not raw:
        return ""
    # Already normalised on insert (YYYY-MM-DD) so a slice is enough.
    if len(raw) >= 7 and raw[4] == "-":
        return raw[:7]
    return ""


def _row_in_month(row: dict, month: str) -> bool:
    """`month` is 'all', '' (no filter, alias for 'all'), or 'YYYY-MM'."""
    if not month or month == "all":
        return True
    return _row_month(row) == month


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
        m = _row_month(r)
        if not m:
            continue
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


def stats(month: str | None = None, reference: str | None = None) -> dict:
    """Quick KPIs for the dashboard header.

    `month` is either:
      - None / "" / "all" → compute over ALL candidates (no filter)
      - 'YYYY-MM' (e.g. '2025-03') → only count candidates whose `date`
        falls in that calendar month.

    `reference` when set limits every aggregate to one handler/referrer —
    used so referrers never see other people's revenue.
    """
    scope_key: str | None = None
    if reference and str(reference).strip().lower() not in ("", "all"):
        scope_key = _reference_key(str(reference).strip())

    all_rows = list_candidates()
    if scope_key:
        all_rows = [
            r for r in all_rows
            if _reference_key(r.get("reference") or "") == scope_key
        ]
    if month and month != "all":
        rows = [r for r in all_rows if _row_in_month(r, month)]
    else:
        rows = all_rows

    total = len(rows)
    by_stage = {s: 0 for s in VALID_STAGES}
    revenue = 0
    revenue_by_tech: dict[str, int] = {}
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
    for r in rows:
        st = r.get("stage") or "in_progress"
        by_stage[st] = by_stage.get(st, 0) + 1
        amt = int(r.get("payment") or 0)
        is_consultancy = bool(r.get("consultancy"))
        service_type = _normalise_service_type(r.get("service_type"), r)
        interview_scope = _normalise_interview_scope(r.get("interview_scope"), r)
        fallback = baseline_for_service(
            service_type,
            consultancy=is_consultancy,
            interview_scope=interview_scope,
        )
        expected = int(r.get("expected_payment") or fallback) or fallback
        balance = max(0, expected - amt)
        # Handler is owed this share of every rupee the client actually paid.
        # Computed per-row so partial payments accrue commission gradually.
        handler_share = (amt * HANDLER_COMMISSION_PCT) // 100
        revenue += amt
        expected_total += expected
        if is_consultancy:
            consultancy_count   += 1
            consultancy_revenue += amt
        else:
            direct_count   += 1
            direct_revenue += amt
        if balance > 0:
            pending_total += balance
            pending_count += 1
            if not (r.get("follow_up") or "").strip():
                pending_no_remark += 1
        tech = (r.get("technology") or "Unspecified").strip() or "Unspecified"
        revenue_by_tech[tech] = revenue_by_tech.get(tech, 0) + amt
        if st == "completed":
            completed_revenue += amt

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
                "consultancy_count": 0,
            }
            perf[ref_key] = bucket
        else:
            bucket["name"] = _prefer_reference_display(bucket["name"], ref_raw)
        bucket["count"] += 1
        if st in bucket:
            bucket[st] += 1
        bucket["revenue_total"] += amt
        bucket["auto_earnings_total"] += handler_share
        if is_consultancy:
            bucket["consultancy_count"] += 1
        if st == "completed":
            bucket["revenue_completed"] += amt
            bucket["auto_earnings_completed"] += handler_share
        if balance > 0:
            bucket["pending_total"] += balance
            bucket["pending_count"] += 1

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
                "consultancy_count": 0,
            }
        else:
            perf[ref_key]["name"] = _prefer_reference_display(perf[ref_key]["name"], ref)

    total_handler_commission    = 0
    total_handler_salary        = 0
    total_handler_paid_out      = 0

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

        # Salary-side fields (NEW). Older clients ignore these.
        p["commission_total"]  = commission
        p["salary_total"]      = salary
        p["salary_monthly"]    = int(salary_bucket.get("monthly_salary") or 0)
        p["salary_active"]     = bool(salary_bucket.get("monthly_salary"))

        # Owed = commission + salary. Overwrite auto_earnings_total so
        # every existing UI bit (chips, "Pay X ₹Y" list, AllExpenses
        # modal header) automatically picks up the higher number.
        p["auto_earnings_total"] = owed

        # New canonical fields used by the UI going forward.
        p["paid_out_total"]    = paid_out
        p["paid_out_count"]    = int(exp_bucket.get("count") or 0)
        p["net_payable"]       = owed - paid_out
        p["commission_pct"]    = HANDLER_COMMISSION_PCT

        # Backwards-compat aliases so older client bundles keep rendering
        # something sensible until the next refresh:
        p["earnings_total"]    = owed         # was: commission rows
        p["deductions_total"]  = paid_out     # was: non-commission rows
        p["net_earning"]       = owed - paid_out
        p["expenses_total"]    = paid_out
        p["expenses_count"]    = int(exp_bucket.get("count") or 0)
        p["net_completed"]     = int(p.get("revenue_completed") or 0) - paid_out

        total_handler_commission += commission
        total_handler_salary     += salary
        total_handler_paid_out   += paid_out

    total_handler_auto_earnings = total_handler_commission + total_handler_salary

    top_tech = sorted(revenue_by_tech.items(), key=lambda kv: kv[1], reverse=True)[:5]
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

    return {
        "total": total,
        "by_stage": by_stage,
        "revenue_total": revenue,
        "revenue_completed": completed_revenue,
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
        "net_handler_payout":           total_handler_auto_earnings - total_handler_paid_out,
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
        # Kept for backwards-compat with anything still consuming the old
        # by-count list; new UI uses `top_performers`.
        "top_references": [
            {"name": p["name"], "count": p["count"]}
            for p in sorted(perf.values(), key=lambda b: b["count"], reverse=True)[:5]
        ],
        "top_performers": top_performers,
        "updated_at": _load().get("updated_at"),
    }


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
    """Remove a proof from the candidate + delete its file from disk."""
    cdata = _load()
    rows = cdata.get("candidates") or []
    for r in rows:
        if r.get("id") != cid:
            continue
        proofs = list(r.get("proofs") or [])
        for i, p in enumerate(proofs):
            if p.get("id") == pid:
                path = os.path.join(_proof_dir(cid), p["filename"])
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
