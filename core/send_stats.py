"""Rolling send history per account slot — campaign cycles vs forwarding."""

from __future__ import annotations

import json
import os
import threading
import time
from typing import Dict, Literal

from core.config import STATE_DIR
from core.stats_reset import get_effective_cutoff

SendKind = Literal["campaign", "forward"]
VALID_KINDS = frozenset({"campaign", "forward"})

WINDOW_SECONDS = 86400  # 24 hours
_lock = threading.Lock()
_cache: Dict[str, tuple[float, dict[str, int]]] = {}  # slot -> (cached_at, counts)


def _normalize_mode(mode: str | None) -> str | None:
    if not mode:
        return None
    m = str(mode).strip().lower()
    if m in ("forward", "forwarding"):
        return "forward"
    if m in ("campaign", "camp"):
        return "campaign"
    return m


def _stats_path(slot: str, mode: str | None = None) -> str:
    os.makedirs(os.path.join(STATE_DIR, slot), exist_ok=True)
    norm = _normalize_mode(mode)
    if norm in ("forward", "campaign"):
        return os.path.join(STATE_DIR, slot, f"send_history_{norm}.json")
    return os.path.join(STATE_DIR, slot, "send_history.json")


def _normalize_events(data) -> list[dict]:
    """Migrate legacy timestamp lists to {t, kind} events."""
    if isinstance(data, list):
        out = []
        for item in data:
            if isinstance(item, (int, float)):
                out.append({"t": float(item), "kind": "campaign"})
            elif isinstance(item, dict) and item.get("t") is not None:
                kind = (item.get("kind") or "campaign").strip().lower()
                if kind not in VALID_KINDS:
                    kind = "campaign"
                out.append({"t": float(item["t"]), "kind": kind})
        return out
    if isinstance(data, dict):
        if isinstance(data.get("events"), list):
            return _normalize_events(data["events"])
        if isinstance(data.get("timestamps"), list):
            return _normalize_events(data["timestamps"])
    return []


def _load_events(slot: str) -> list[dict]:
    path = _stats_path(slot)
    if not os.path.exists(path):
        return []
    try:
        with open(path, "r", encoding="utf-8") as f:
            return _normalize_events(json.load(f))
    except Exception:
        return []


def _save_events(slot: str, events: list[dict]) -> None:
    path = _stats_path(slot)
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump({"events": events}, f, indent=0)
    except Exception:
        pass


def invalidate_cache(slot: str | None = None) -> None:
    with _lock:
        if slot:
            keys = [k for k in _cache if k[0] == slot]
            for key in keys:
                _cache.pop(key, None)
        else:
            _cache.clear()


def _filter_since_cutoff(
    events: list[dict],
    slot: str,
    *,
    now: float | None = None,
    kind: SendKind | None = None,
) -> list[dict]:
    cutoff = get_effective_cutoff(slot, now)
    out = []
    for ev in events:
        t = float(ev.get("t") or 0)
        if t < cutoff:
            continue
        if kind is not None and (ev.get("kind") or "campaign") != kind:
            continue
        out.append(ev)
    return out


def count_since_cutoff(slot: str, cutoff: float, kind: SendKind | None = None) -> int:
    """Count sends since explicit cutoff; optional filter by posting kind."""
    if not slot:
        return 0
    raw = _load_events(slot)
    return sum(
        1
        for ev in raw
        if float(ev.get("t") or 0) >= cutoff
        and (kind is None or (ev.get("kind") or "campaign") == kind)
    )


def record_send(slot: str, kind: SendKind = "campaign") -> int:
    """Record one successful group post; returns total in window for that kind."""
    if not slot:
        return 0
    k = kind if kind in VALID_KINDS else "campaign"
    now = time.time()
    with _lock:
        events = _filter_since_cutoff(_load_events(slot), slot, now=now)
        events.append({"t": now, "kind": k})
        _save_events(slot, events)
        counts = {
            "campaign": len(_filter_since_cutoff(events, slot, now=now, kind="campaign")),
            "forward": len(_filter_since_cutoff(events, slot, now=now, kind="forward")),
            "total": len(events),
        }
        _cache[slot] = (now, counts)
        return counts[k]


def get_last_post_timestamp(slot: str) -> float | None:
    """Latest successful campaign or forward post (and group_send history)."""
    if not slot:
        return None
    last: float | None = None
    for ev in _load_events(slot):
        try:
            t = float(ev.get("t") or 0)
        except (TypeError, ValueError):
            continue
        if t > 0:
            last = max(last or 0.0, t)
    try:
        from core.group_send_stats import get_last_group_send_timestamp

        g = get_last_group_send_timestamp(slot)
        if g:
            last = max(last or 0.0, float(g))
    except Exception:
        pass
    return last


def count_24h(slot: str, kind: SendKind | None = None) -> int:
    """Posts since last reset (or rolling 24h); optional kind filter."""
    if not slot:
        return 0
    norm = _normalize_mode(mode)
    now = time.time()
    with _lock:
        cached = _cache.get(slot)
        if cached and now - cached[0] < 30 and kind is None:
            return cached[1].get("total", 0)
        events = _load_events(slot)
        filtered = _filter_since_cutoff(events, slot, now=now, kind=kind)
        if len(filtered) != len(events):
            _save_events(slot, _filter_since_cutoff(events, slot, now=now))
        if kind:
            return len(filtered)
        total = len(_filter_since_cutoff(events, slot, now=now))
        counts = {
            "campaign": len(_filter_since_cutoff(events, slot, now=now, kind="campaign")),
            "forward": len(_filter_since_cutoff(events, slot, now=now, kind="forward")),
            "total": total,
        }
        _cache[slot] = (now, counts)
        return total
