#!/usr/bin/env python3
"""Backfill actionable Mail Alerts from legacy pending recruitment events.

Dry-run is the default. Pass ``--apply`` to persist alerts. Source messages and
recruitment events are never deleted or rewritten.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.db.connection import get_connection
from core import recruitment_mail_store as store


def _rows(cur) -> list[dict[str, Any]]:
    names = [item.name for item in cur.description]
    return [dict(zip(names, row)) for row in cur.fetchall()]


def candidates() -> list[dict[str, Any]]:
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute(
            """
            SELECT e.*, m.subject, m.sender_name, m.sender_email,
              m.provider_message_id,
              a.id AS analysis_id, a.classification AS analysis_classification,
              a.candidate_status AS analysis_candidate_status,
              a.confidence AS analysis_confidence,
              n.id AS notification_id,
              n.dismissed_at AS notification_dismissed_at
            FROM ai_recruitment_events e
            JOIN mailbox_messages m ON m.id=e.mailbox_message_id
            JOIN mail_ai_analyses a ON a.mailbox_message_id=e.mailbox_message_id
            LEFT JOIN mail_monitoring_notifications n
              ON n.ai_recruitment_event_id=e.id
            WHERE e.review_status='PENDING'
            ORDER BY m.sent_at DESC, e.created_at DESC
            """
        )
        return _rows(cur)


def analysis_for(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": row["analysis_id"],
        "classification": row.get("classification")
        or store.canonical_classification(
            row.get("structured_result") or {},
            row.get("primary_status"),
        )
        or row.get("analysis_classification"),
        "candidate_status": row.get("candidate_status")
        or row.get("analysis_candidate_status"),
        "confidence": row.get("analysis_confidence") or row.get("confidence"),
    }


def calendar_uid(row: dict[str, Any]) -> str:
    structured = row.get("structured_result") or {}
    return str((structured.get("calendar") or {}).get("uid") or "").strip()


def restore_notification(notification_id: str) -> dict[str, Any]:
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute(
            """UPDATE mail_monitoring_notifications SET
              dismissed_at=NULL,is_read=false,read_at=NULL,
              is_reviewed=false,reviewed_at=NULL,reviewed_by=NULL,
              review_notes=NULL,updated_at=now()
              WHERE id=%s RETURNING *""",
            (notification_id,),
        )
        names = [item.name for item in cur.description]
        return dict(zip(names, cur.fetchone()))


def stale_interview_notification_ids() -> list[str]:
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute(
            """SELECT n.id
              FROM mail_monitoring_notifications n
              JOIN ai_recruitment_events e ON e.id=n.ai_recruitment_event_id
              WHERE n.dismissed_at IS NULL
                AND n.classification IN(
                  'interview_confirmed','interview_rescheduled',
                  'interview_shortlisted','interview_cancelled'
                )
                AND COALESCE(
                  e.structured_result->'interview'->>'date',
                  e.interview_date::text,
                  ''
                ) < CURRENT_DATE::text"""
        )
        return [str(row[0]) for row in cur.fetchall()]


def dismiss_stale_interview_notifications(ids: list[str]) -> int:
    if not ids:
        return 0
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute(
            """UPDATE mail_monitoring_notifications SET
              dismissed_at=now(),is_read=true,
              read_at=COALESCE(read_at,now()),updated_at=now()
              WHERE id=ANY(%s) RETURNING id""",
            (ids,),
        )
        return len(cur.fetchall())


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()

    seen_calendar_uids: set[str] = set()
    routed: list[dict[str, Any]] = []
    stale_ids = stale_interview_notification_ids()
    for row in candidates():
        analysis = analysis_for(row)
        source = {
            "subject": row.get("subject"),
            "sender_name": row.get("sender_name"),
            "sender_email": row.get("sender_email"),
        }
        if not store.should_route_to_mail_alert(row, analysis, source=source):
            continue
        uid = calendar_uid(row)
        if uid and uid in seen_calendar_uids:
            continue
        if uid:
            seen_calendar_uids.add(uid)
        existing_id = row.get("notification_id")
        if existing_id and not row.get("notification_dismissed_at"):
            continue
        if args.apply:
            notification = (
                restore_notification(str(existing_id))
                if existing_id
                else store.create_monitoring_notification(row, analysis)
            )
        else:
            notification = {"id": str(existing_id or "dry-run")}
        if notification:
            routed.append(
                {
                    "event_id": row["id"],
                    "notification_id": notification["id"],
                    "candidate_id": row["candidate_id"],
                    "classification": analysis["classification"],
                    "subject": row.get("subject"),
                    "action": "restored" if existing_id else "created",
                }
            )

    print(
        json.dumps(
            {
                "mode": "apply" if args.apply else "dry-run",
                "created": len(routed),
                "alerts": routed,
                "stale_interviews_found": len(stale_ids),
                "stale_interviews_archived": (
                    dismiss_stale_interview_notifications(stale_ids)
                    if args.apply
                    else 0
                ),
            },
            indent=2,
            default=str,
        )
    )


if __name__ == "__main__":
    main()
