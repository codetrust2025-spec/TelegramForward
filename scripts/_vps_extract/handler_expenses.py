"""Persistent ledger of expenses incurred for a handler / reference
(the person who refers candidates — e.g. Thrilok, Venugopal, Referrer One).

This is intentionally separate from the per-candidate `expenses` free-text
field. Those were one-off operator notes ("12000 gym"). This new ledger is
a structured list with amount + category + date so we can:
  - aggregate spend per handler,
  - filter by month,
  - compute net contribution = revenue_completed - expenses_total.

Schema (one row):

    {
        "id":         "short id",
        "reference":  "handler / referrer name (case-insensitive match)",
        "amount":     <int rupees>,
        "category":   "commission | travel | food | gym | equipment | "
                      "marketing | software | other",
        "note":       "free text",
        "date":       "YYYY-MM-DD",
        "created_at": ISO ts,
        "updated_at": ISO ts,
    }

Stored as JSON-on-disk under `data/handler_expenses.json`, same pattern
as the rest of the project.
"""
from __future__ import annotations

import json
import os
import uuid
from datetime import datetime, timezone
from threading import Lock

from core.config import DATA_DIR

_FILE = os.path.join(DATA_DIR, "handler_expenses.json")
_lock = Lock()

VALID_CATEGORIES = {
    "commission", "travel", "food", "gym",
    "equipment", "marketing", "software", "other",
}

CATEGORY_LABELS = {
    "commission":  "Commission / referral fee",
    "travel":      "Travel / fuel",
    "food":        "Food / meals",
    "gym":         "Gym / health",
    "equipment":   "Equipment",
    "marketing":   "Marketing",
    "software":    "Software / tools",
    "other":       "Other",
}


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _new_id() -> str:
    return uuid.uuid4().hex[:10]


def _empty() -> dict:
    return {"expenses": [], "updated_at": None}


def _load() -> dict:
    with _lock:
        if not os.path.exists(_FILE):
            return _empty()
        try:
            with open(_FILE, encoding="utf-8") as f:
                data = json.load(f)
            if not isinstance(data, dict):
                return _empty()
            data.setdefault("expenses", [])
            data.setdefault("updated_at", None)
            return data
        except (OSError, json.JSONDecodeError):
            return _empty()


def _save(data: dict) -> None:
    os.makedirs(os.path.dirname(_FILE), exist_ok=True)
    data["updated_at"] = _now_iso()
    with _lock:
        tmp = _FILE + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        os.replace(tmp, _FILE)


def _coerce_amount(value) -> int:
    if value is None or value == "":
        return 0
    if isinstance(value, (int, float)):
        return max(0, int(value))
    s = str(value).strip().replace("₹", "").replace(",", "").replace(" ", "")
    if not s or s.lower() in {"nan", "-"}:
        return 0
    try:
        return max(0, int(float(s)))
    except ValueError:
        return 0


def _clean_str(value, *, default: str = "") -> str:
    if value is None:
        return default
    s = str(value).strip()
    return s or default


def _row_month(row: dict) -> str:
    raw = (row.get("date") or "").strip()
    if not raw:
        return ""
    if len(raw) >= 7 and raw[4] == "-":
        return raw[:7]
    return ""


_ALLOWED_FIELDS = {"reference", "amount", "category", "note", "date"}


def _normalise(record: dict, *, existing: dict | None = None) -> dict:
    base = dict(existing) if existing else {}
    category = _clean_str(
        record.get("category", base.get("category", "other"))
    ).lower().replace(" ", "_").replace("-", "_")
    if category not in VALID_CATEGORIES:
        category = "other"
    out = {
        "id":         base.get("id") or _new_id(),
        "reference":  _clean_str(record.get("reference", base.get("reference"))),
        "amount":     _coerce_amount(record.get("amount", base.get("amount"))),
        "category":   category,
        "note":       _clean_str(record.get("note", base.get("note")))[:240],
        "date":       _clean_str(record.get("date", base.get("date"))),
        "created_at": base.get("created_at") or _now_iso(),
        "updated_at": _now_iso(),
    }
    return out


# ── Public API ──────────────────────────────────────────────────────────────

def list_expenses(*, reference: str | None = None, month: str | None = None) -> list[dict]:
    """Most-recent first. Filter by reference (case-insensitive exact match)
    and/or by month ('YYYY-MM')."""
    rows = list((_load().get("expenses") or []))
    if reference:
        ref_lc = reference.strip().lower()
        rows = [r for r in rows if (r.get("reference") or "").strip().lower() == ref_lc]
    if month and month != "all":
        rows = [r for r in rows if _row_month(r) == month]
    rows.sort(key=lambda r: (r.get("date") or "", r.get("created_at") or ""), reverse=True)
    return rows


def create_expense(record: dict) -> dict:
    data = _load()
    row = _normalise(record)
    data.setdefault("expenses", []).append(row)
    _save(data)
    return row


def update_expense(eid: str, patch: dict) -> dict | None:
    data = _load()
    rows = data.get("expenses") or []
    for i, r in enumerate(rows):
        if r.get("id") == eid:
            allowed = {k: v for k, v in patch.items() if k in _ALLOWED_FIELDS}
            rows[i] = _normalise(allowed, existing=r)
            data["expenses"] = rows
            _save(data)
            return rows[i]
    return None


def delete_expense(eid: str) -> bool:
    data = _load()
    before = data.get("expenses") or []
    after = [r for r in before if r.get("id") != eid]
    if len(after) == len(before):
        return False
    data["expenses"] = after
    _save(data)
    return True


def summary_by_handler(month: str | None = None) -> dict[str, dict]:
    """Return `{reference_lowercase: {name, total, count, by_category}}`.

    The ledger no longer cares whether a row is "earning" or "deduction" —
    every entry represents money the operator has ALREADY PAID OUT for
    the handler (their commission disbursement, their fuel, their food,
    etc.). The handler's owed-amount is auto-computed elsewhere from the
    50% rule. Net payable to the handler = owed − total of this ledger.

    The lowercase key lets the candidates module match against its own
    `reference` field without worrying about casing. The display name in
    `name` is taken from the most-recently-seen casing (since operators
    sometimes type 'Thrilok' / 'THRILOK' / 'thrilok' interchangeably)."""
    rows = list_expenses(month=month)
    out: dict[str, dict] = {}
    for r in rows:
        ref = (r.get("reference") or "").strip()
        if not ref:
            continue
        key = ref.lower()
        bucket = out.setdefault(key, {
            "name": ref, "total": 0, "count": 0, "by_category": {},
        })
        amount = int(r.get("amount") or 0)
        bucket["total"] += amount
        bucket["count"] += 1
        cat = r.get("category") or "other"
        bucket["by_category"][cat] = bucket["by_category"].get(cat, 0) + amount
        bucket["name"] = ref
    return out


def total_for_handler(reference: str, *, month: str | None = None) -> int:
    """Convenience: how many rupees was spent on this handler in the
    given month (or all-time if `month` is None/'all')."""
    if not reference:
        return 0
    return sum(int(r.get("amount") or 0) for r in list_expenses(
        reference=reference, month=month,
    ))


def available_months() -> list[dict]:
    """For the modal's filter dropdown — same shape as candidate_store
    so the frontend can reuse the renderer."""
    rows = _load().get("expenses") or []
    counts: dict[str, int] = {}
    for r in rows:
        m = _row_month(r)
        if not m:
            continue
        counts[m] = counts.get(m, 0) + 1
    today = datetime.now(timezone.utc)
    current = today.strftime("%Y-%m")
    counts.setdefault(current, 0)
    sorted_months = sorted(counts.keys(), reverse=True)
    month_names = ("Jan", "Feb", "Mar", "Apr", "May", "Jun",
                   "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")
    out = []
    for m in sorted_months:
        try:
            y, mo = m.split("-")
            label = f"{month_names[int(mo) - 1]} {y}"
        except (ValueError, IndexError):
            label = m
        out.append({
            "value": m, "label": label, "count": counts[m],
            "is_current": m == current,
        })
    return out
