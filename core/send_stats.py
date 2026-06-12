"""Rolling send history per account — counts and hourly buckets for dashboard charts."""

from __future__ import annotations

import json
import os
import threading
import time
from typing import Iterable

from core.config import STATE_DIR
from core.stats_reset import get_effective_cutoff

WINDOW_SECONDS = 86400
_lock = threading.Lock()
_cache: dict[tuple[str, str | None], tuple[float, int]] = {}


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


def _extract_timestamps(raw) -> list[float]:
    if isinstance(raw, list):
        out: list[float] = []
        for item in raw:
            if isinstance(item, (int, float)):
                out.append(float(item))
            elif isinstance(item, dict):
                ts = item.get("ts") or item.get("timestamp") or item.get("time")
                if ts is not None:
                    out.append(float(ts))
        return out
    if isinstance(raw, dict):
        if isinstance(raw.get("timestamps"), list):
            return _extract_timestamps(raw["timestamps"])
        out = []
        for value in raw.values():
            if isinstance(value, (int, float)):
                out.append(float(value))
            elif isinstance(value, dict):
                ts = value.get("ts") or value.get("timestamp") or value.get("time")
                if ts is not None:
                    out.append(float(ts))
        return out
    return []


def _load_timestamps(slot: str, mode: str | None = None) -> list[float]:
    path = _stats_path(slot, mode)
    if not os.path.exists(path):
        return []
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        return _extract_timestamps(data)
    except Exception:
        return []


def _save_timestamps(slot: str, timestamps: list[float], mode: str | None = None) -> None:
    path = _stats_path(slot, mode)
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump({"timestamps": timestamps}, f, indent=0)
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
    timestamps: Iterable[float],
    slot: str,
    *,
    now: float | None = None,
    cutoff: float | None = None,
) -> list[float]:
    floor = cutoff if cutoff is not None else get_effective_cutoff(slot, now)
    return [float(t) for t in timestamps if float(t) >= floor]


def count_since_cutoff(slot: str, cutoff: float, mode: str | None = None) -> int:
    if not slot:
        return 0
    raw = _load_timestamps(slot, mode)
    return sum(1 for t in raw if float(t) >= cutoff)


def record_send(slot: str, mode: str | None = None) -> int:
    """Record one successful post; returns count in the active window."""
    return record_send_batch(slot, 1, mode)


def record_send_batch(slot: str, count: int, mode: str | None = None) -> int:
    """Record N successful posts in one write; returns count in the active window."""
    if not slot or count <= 0:
        return count_24h(slot, mode)
    norm = _normalize_mode(mode)
    now = time.time()
    with _lock:
        ts = _filter_since_cutoff(_load_timestamps(slot, norm), slot, now=now)
        ts.extend([now] * int(count))
        _save_timestamps(slot, ts, norm)
        if norm:
            legacy = _filter_since_cutoff(_load_timestamps(slot, None), slot, now=now)
            legacy.extend([now] * int(count))
            _save_timestamps(slot, legacy, None)
        total = len(ts)
        _cache[(slot, norm)] = (now, total)
        return total


def count_24h(slot: str, mode: str | None = None) -> int:
    """Successful sends since IST day start or today's manual reset."""
    if not slot:
        return 0
    norm = _normalize_mode(mode)
    now = time.time()
    with _lock:
        cached = _cache.get((slot, norm))
        if cached and now - cached[0] < 30:
            return cached[1]
        raw = _load_timestamps(slot, norm)
        ts = _filter_since_cutoff(raw, slot, now=now)
        if len(ts) != len(raw):
            _save_timestamps(slot, ts, norm)
        count = len(ts)
        _cache[(slot, norm)] = (now, count)
        return count


def count_24h_for_mode(slot: str, mode: str | None = None) -> int:
    """Mode-specific send count; attributes legacy send_history when mode files are empty."""
    if not slot:
        return 0
    norm = _normalize_mode(mode)
    direct = count_24h(slot, norm)
    if direct > 0 or not norm:
        return direct
    legacy = count_24h(slot, None)
    if legacy <= 0:
        return 0
    try:
        from core.posting_mode import load_posting_mode

        pm = load_posting_mode(slot)
        if norm == "forward" and pm.forwarding_enabled and not pm.campaign_enabled:
            return legacy
        if norm == "campaign" and pm.campaign_enabled and not pm.forwarding_enabled:
            return legacy
    except Exception:
        pass
    return 0


def get_last_post_timestamp(slot: str) -> float | None:
    """Unix time of the most recent successful post (legacy + mode-specific history)."""
    if not slot:
        return None
    latest: float | None = None
    for mode in (None, "forward", "campaign"):
        for ts in _load_timestamps(slot, mode):
            t = float(ts)
            if latest is None or t > latest:
                latest = t
    try:
        from core.group_send_stats import get_last_group_send_timestamp

        group_ts = get_last_group_send_timestamp(slot)
        if group_ts is not None and (latest is None or float(group_ts) > latest):
            latest = float(group_ts)
    except Exception:
        pass
    return latest


def hourly_buckets(
    slots: list[str],
    *,
    mode: str | None = None,
    bucket_count: int = 24,
    now: float | None = None,
) -> list[int]:
    """Hourly send counts, oldest bucket first (24h ago → current hour)."""
    if bucket_count <= 0:
        return []
    norm = _normalize_mode(mode)
    now = now or time.time()
    window_start = now - bucket_count * 3600
    buckets = [0] * bucket_count
    for slot in slots:
        if not slot:
            continue
        cutoff = max(window_start, get_effective_cutoff(slot, now))
        for ts in _load_timestamps(slot, norm):
            t = float(ts)
            if t < cutoff or t > now:
                continue
            age_hours = int((now - t) // 3600)
            if age_hours >= bucket_count:
                continue
            idx = bucket_count - 1 - age_hours
            buckets[idx] += 1
    return buckets


def hourly_bucket_labels(bucket_count: int = 24, now: float | None = None) -> list[str]:
    """IST clock labels for rolling hourly buckets (oldest → newest)."""
    from datetime import timedelta

    from core.ist_time import ist_now

    now_ts = now or time.time()
    labels: list[str] = []
    for i in range(bucket_count):
        if i % 6 != 0 and i != bucket_count - 1:
            labels.append("")
            continue
        age = bucket_count - 1 - i
        dt = ist_now(now_ts) - timedelta(hours=age)
        labels.append(dt.strftime("%H:%M"))
    return labels
