"""Postgres persistence for candidates_store (production)."""

from __future__ import annotations

import json
from datetime import datetime, timezone

from core.db.connection import get_connection


def pg_load() -> dict:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT payload
                FROM candidates_store
                ORDER BY COALESCE((payload->>'logged_date')::text, ''), id
                """
            )
            rows = []
            for (payload,) in cur.fetchall():
                if isinstance(payload, dict):
                    rows.append(payload)
                elif isinstance(payload, str):
                    try:
                        rows.append(json.loads(payload))
                    except json.JSONDecodeError:
                        continue
    return {
        "candidates": rows,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }


def pg_save(data: dict) -> None:
    candidates = list(data.get("candidates") or [])
    updated_at = data.get("updated_at")
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM candidates_store")
            for row in candidates:
                if not isinstance(row, dict):
                    continue
                cid = (row.get("id") or "").strip()
                if not cid:
                    continue
                payload = dict(row)
                if updated_at:
                    payload.setdefault("_store_updated_at", updated_at)
                cur.execute(
                    """
                    INSERT INTO candidates_store (id, payload)
                    VALUES (%s, %s::jsonb)
                    ON CONFLICT (id) DO UPDATE SET payload = EXCLUDED.payload
                    """,
                    (cid, json.dumps(payload, ensure_ascii=False)),
                )
