#!/usr/bin/env python3
import re

_IMPERSONAL_LEAD_NAMES = frozenset({
    "codex", "giguyz", "services", "support", "llp", "interview", "admin",
    "user", "telegram", "unknown", "customer", "client", "team",
})
_INITIALS_NAME_RE = re.compile(
    r"^(?:[A-Za-z]\.){1,5}[A-Za-z]?\.?$|^[A-Za-z]{1,2}\.?$",
)

def _is_initials_or_abbrev(name: str) -> bool:
    s = (name or "").strip()
    if not s:
        return True
    compact = s.replace(".", "").replace(" ", "")
    if _INITIALS_NAME_RE.match(s):
        return True
    if 1 < len(compact) <= 3 and compact.isalpha() and compact.isupper():
        return True
    return False

def _is_impersonal_lead_name(name: str) -> bool:
    n = (name or "").strip().lower()
    if not n:
        return True
    first = n.split()[0]
    if first in _IMPERSONAL_LEAD_NAMES:
        return True
    if any(w in n for w in (" llp", " services", " support", " pvt", " ltd", " company")):
        return True
    return False

def _normalize_first_name_token(token: str) -> str:
    t = (token or "").strip().lstrip("@")
    if not t or len(t) < 2 or not t[0].isalpha():
        return ""
    if t.startswith("@") or t.replace("_", "").isdigit():
        return ""
    if _is_initials_or_abbrev(t) or _is_impersonal_lead_name(t):
        return ""
    if not any(ch.isalpha() for ch in t):
        return ""
    return t[0].upper() + t[1:].lower() if len(t) > 1 else t.upper()

def _first_name(lead):
    raw = (lead.get("name") or "").strip() if lead else ""
    if not raw or _is_impersonal_lead_name(raw):
        return ""
    parts = [p for p in raw.split() if p.strip()]
    if not parts:
        return ""
    for part in parts:
        name = _normalize_first_name_token(part)
        if name:
            return name
    return ""

for lead, want in [
    ({"name": "R.B."}, ""),
    ({"name": "R.B. Madhu"}, "Madhu"),
    ({"name": "Madhu"}, "Madhu"),
    ({"name": "Priya Sharma"}, "Priya"),
    ({"name": "A.K."}, ""),
    ({"name": "Karthik Prasad"}, "Karthik"),
]:
    got = _first_name(lead)
    print(f"{'OK' if got==want else 'FAIL'} {lead['name']!r} -> {got!r} want {want!r}")
