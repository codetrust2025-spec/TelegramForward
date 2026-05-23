"""Rolling 24h count of successful message sends per account slot."""

from __future__ import annotations

import json
import os
import threading
import time
from typing import Dict

from core.config import STATE_DIR
from core.stats_reset import get_effective_cutoff

WINDOW_SECONDS = 86400  # 24 hours
_lock = threading.Lock()
_cache: Dict[str, tuple[float, int]] = {}  # slot -> (cached_at, count)


def _stats_path(slot: str) -> str:
    os.makedirs(os.path.join(STATE_DIR, slot), exist_ok=True)
    return os.path.join(STATE_DIR, slot, "send_history.json")


def _load_timestamps(slot: str) -> list[float]:
    path = _stats_path(slot)
    if not os.path.exists(path):
        return []
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, list):
            return [float(t) for t in data]
        if isinstance(data, dict) and isinstance(data.get("timestamps"), list):
            return [float(t) for t in data["timestamps"]]
    except Exception:
        pass
    return []


def _save_timestamps(slot: str, timestamps: list[float]) -> None:
    path = _stats_path(slot)
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump({"timestamps": timestamps}, f, indent=0)
    except Exception:
        pass


def invalidate_cache(slot: str | None = None) -> None:
    """Clear cached counts after a stats reset."""
    with _lock:
        if slot:
            _cache.pop(slot, None)
        else:
            _cache.clear()


def _filter_since_cutoff(
    timestamps: list[float],
    slot: str,
    *,
    now: float | None = None,
) -> list[float]:
    cutoff = get_effective_cutoff(slot, now)
    return [t for t in timestamps if t >= cutoff]


def count_since_cutoff(slot: str, cutoff: float) -> int:
    """Count send timestamps >= explicit cutoff (used by daily_stats)."""
    if not slot:
        return 0
    raw = _load_timestamps(slot)
    return sum(1 for t in raw if t >= cutoff)


def record_send(slot: str) -> int:
    """Record one successful post; returns count in last 24h."""
    if not slot:
        return 0
    now = time.time()
    with _lock:
        ts = _filter_since_cutoff(_load_timestamps(slot), slot, now=now)
        ts.append(now)
        _save_timestamps(slot, ts)
        count = len(ts)
        _cache[slot] = (now, count)
        return count


def count_24h(slot: str) -> int:
    """Successful forwards since last reset, or rolling last 24h if never reset."""
    if not slot:
        return 0
    now = time.time()
    with _lock:
        cached = _cache.get(slot)
        if cached and now - cached[0] < 30:
            return cached[1]
        raw = _load_timestamps(slot)
        ts = _filter_since_cutoff(raw, slot, now=now)
        if len(ts) != len(raw):
            _save_timestamps(slot, ts)
        count = len(ts)
        _cache[slot] = (now, count)
        return count
