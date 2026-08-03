"""Give already-blocked notifications the reason they were blocked for.

The failure code has always been recorded on the booking audit; it just never
reached the notification row. Rows blocked before that changed would otherwise
keep showing a bare "Automatic Booking Blocked" forever, so they are filled in
from the audit they already have.

    python scripts/backfill_booking_block_reasons.py --dry-run
    python scripts/backfill_booking_block_reasons.py --apply

Only rows with no reason yet are touched, so a re-run is a no-op and nothing a
live booking has written is overwritten.
"""
from __future__ import annotations

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.recruitment_mail_store import get_connection, use_postgres  # noqa: E402
from services import booking_block_reasons  # noqa: E402

# The most recent audit for a notification is the decision that row reflects.
SELECT = """
SELECT n.id, n.candidate_status, n.booking_status, n.interview_date, n.interview_time,
       a.failure_code, a.failure_message
  FROM mail_monitoring_notifications n
  LEFT JOIN LATERAL (
        SELECT failure_code, failure_message
          FROM interview_auto_booking_audit
         WHERE id = n.booking_audit_id
         LIMIT 1
  ) a ON true
 WHERE n.booking_block_reason IS NULL
   AND n.booking_status IN ('Blocked', 'Processing Failed', 'Review Required')
 ORDER BY n.created_at DESC
"""


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    if args.apply == args.dry_run:
        print("Choose exactly one of --apply or --dry-run", file=sys.stderr)
        return 2
    if not use_postgres():
        print("Postgres is not configured; nothing to backfill.")
        return 0

    with get_connection() as conn, conn.cursor() as cur:
        cur.execute(SELECT)
        rows = [dict(zip([d.name for d in cur.description], row)) for row in cur.fetchall()]

        print(f"rows without a blocking reason: {len(rows)}")
        updates = []
        for row in rows:
            described = booking_block_reasons.describe(
                row.get("failure_code"),
                # The notification stores the schedule the invite asked for,
                # which is what makes a slot or duplicate reason concrete.
                schedule={"date": row.get("interview_date"), "time": row.get("interview_time")},
            )
            updates.append((described, row))
            print(
                f"  {row['id']}  {row.get('booking_status')}"
                f"  {row.get('failure_code') or '(no audit code)'}"
                f"  -> {described['reason_code']}: {described['reason']}"
            )
        if not updates:
            print("Nothing to backfill.")
            return 0
        if args.dry_run:
            print("\nDry run: nothing was written.")
            return 0

        for described, row in updates:
            cur.execute(
                """UPDATE mail_monitoring_notifications
                      SET booking_block_reason_code=%s, booking_block_reason=%s,
                          booking_failure_code=COALESCE(booking_failure_code,%s),
                          updated_at=now()
                    WHERE id=%s AND booking_block_reason IS NULL""",
                (described["reason_code"], described["reason"],
                 described["internal_code"] or None, row["id"]),
            )
        print(f"\nbackfilled {len(updates)} notification(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
