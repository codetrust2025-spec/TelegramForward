# India Standard Time (IST) display

All **user-visible** dates and times use **IST** (`Asia/Kolkata`, UTC+5:30).

## Dashboard

- Shared helpers: `dashboard/src/utils/istTime.js`
- Logs, inbox, shutdown resume, daily stats reset line, CRM, candidates, admin, forward job ETA, etc.

## Backend (labels shown in UI)

- `core/ist_time.py` — `format_ist_storage_label()`, `format_ist_iso()`, `format_ist_datetime()`
- New membership scans: `joined_updated_at` stored as `YYYY-MM-DD HH:MM IST`
- Chat exports and shutdown resume timestamps formatted for IST

## Legacy data

Strings ending in ` UTC` are still parsed correctly; display is always converted to IST.

Internal storage (unix timestamps, ISO UTC in JSON) is unchanged — only **display** is IST.
