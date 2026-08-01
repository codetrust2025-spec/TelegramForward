# Claude Repository Operating Instructions

Claude follows the same permanent rules as every other human or AI contributor.

## Required reading

Read `PROJECT_RULES.md`, `AGENTS.md`, `DEVELOPMENT_WORKFLOW.md`, and `CONTRIBUTING.md` before changing code. Read `DEPLOYMENT.md` or `RECOVERY.md` before operational work. Those files are authoritative; this file is only a Claude-specific entry point.

## Non-negotiable behavior

- Never develop, commit, or push directly on `main`.
- Start from a clean feature branch based on synchronized `main`.
- Preserve dirty work; never discard user changes.
- Make focused changes and add regression tests for behavior changes.
- Run backend and frontend validation before Pull Request merge.
- Never weaken tests to obtain a passing result.
- Never expose or modify secrets, `.env`, uploads, databases, sessions, logs, caches, runtime JSON, or backups.
- Never deploy from a working directory or unmerged branch.
- Never force-push.
- Never modify Production without explicit deployment authorization and a verified backup.
- Stop on ambiguous business behavior, data-loss risk, secret exposure, unexpected Production dependencies, or failed rollback.

## Standard lifecycle

`Requirements -> Feature branch -> Development -> Tests -> Commit -> Push -> PR -> Required CI -> Optional review -> Merge -> Backup -> Deploy -> Verify -> Monitor`

## Project invariants

- `/bookings/confirm` is the only public booking creation boundary.
- Upload, OCR, AI verification, field changes, and auto-save create no candidate or booking.
- Confirmation is idempotent and failed confirmation creates no partial records.
- Payment reuse uses a transaction reference and is authorized on the backend.
- Production artifacts come from an exact committed Git revision.

At completion, state exactly what changed, what was tested, what was not tested, and whether any remote system changed.
