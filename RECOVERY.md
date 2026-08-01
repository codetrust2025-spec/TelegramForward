# Recovery and Disaster Recovery Manual

This document governs Production incidents, repository drift, failed releases, data restoration, and reconstruction of canonical source.

## Priorities

1. Protect credentials, candidate data, payment evidence, and sessions.
2. Preserve the current stable Production system.
3. Stop active data loss or corruption.
4. Capture evidence without unnecessary mutation.
5. Restore service from verified releases and data.
6. Reconcile Git and Production only after business behavior is understood.

## Immediate actions

- Assign an incident owner and record UTC timestamps.
- Stop deployment automation and concurrent administrative changes.
- Do not clean, reset, reinstall, delete, or overwrite evidence.
- Capture health, PM2, Nginx, disk, database, release pointer, manifest, and marker status.
- Record hashes and permissions, never secret values.
- Rotate exposed credentials without repeating them in reports.
- Roll back to the verified previous release when the current release is unhealthy.

## Production drift recovery

Production can contain a stable hybrid state. Never copy the entire Production directory into Git.

### Never canonical source

`.env`, secrets, uploads/evidence, databases, sessions, logs, caches, runtime JSON/queues/workers, backups, rollback archives, temporary scripts, virtual environments, and dependency caches.

### Canonical-source candidates

Application/frontend source, migrations, dependency declarations/locks, sanitized templates, tests, reviewed automation, build configuration, and documentation.

## Recovery branch procedure

1. Preserve dirty worktrees and record hashes.
2. Create a fresh recovery worktree from the approved Git base.
3. Create a read-only checksum manifest of allowlisted Production source.
4. Compare Production, local, and GitHub behavior, not merely files.
5. Classify each feature as Keep Production, Keep GitHub, Merge both, or Remove.
6. Obtain business approval for the feature matrix.
7. Merge at function/behavior level; never blindly copy complete files.
8. Record each changed file as Production-derived, GitHub-derived, Recovery-worktree-derived, Manually merged, or Newly created.
9. Apply small ordered commits with focused tests and scans.
10. Push only the recovery branch and review through a PR.

Keep Production and GitHub `main` untouched until explicit merge/deployment approval.

Recovery work does not waive branch protection. Recovery branches still require the protected `main` Pull Request, independent approval, resolved conversations, and required passing checks. Any emergency protection change must be separately authorized, time-bounded, logged, restored immediately, and reviewed afterward.

## Data restoration

Verify inventory and checksums before restoring. Restore to an isolated location first whenever possible.

### PostgreSQL

- Validate with `pg_restore --list`.
- Restore into a temporary database for schema/application smoke tests.
- Confirm schema version, critical counts, constraints, and recent data.
- Control writes during final restore.
- Never overwrite the only remaining database copy.

### Runtime files

- Verify ownership, permissions, path, and consumer.
- Restore sessions and credentials without printing contents.
- Preserve current files until replacements are verified.
- Treat candidate uploads and payment/interview evidence as access-controlled sensitive data.

## Release recovery

Prefer rollback of `current`, restart with the protected environment, and verify local/public health, assets, manifest, and APIs. If needed, install a clean artifact of the prior exact Git commit into a new release directory. Restore data only when code rollback cannot recover service. Never patch the active release in place.

## Disaster recovery

1. Provision and harden a clean supported Linux host.
2. Install documented system dependencies.
3. Restore protected configuration from secure backup.
4. Restore PostgreSQL to a new database and verify it.
5. Restore uploads, sessions, and runtime data with least privilege.
6. Install the exact approved release into `releases/<commit>`.
7. Recreate runtime links and the atomic `current` pointer.
8. Configure PM2/Nginx through `current`.
9. Run all offline/live checks in `DEPLOYMENT.md`.
10. Shift traffic only after validation, then monitor and retain forensic evidence.

## Completion criteria

Recovery is complete only when Git and Production hashes match, database checks pass, protected files have correct permissions, processes/integrations are stable, booking/payment invariants hold, backups/rollback remain available, and an incident report records root cause, timeline, evidence, risks, and preventive work.

## Never during recovery

Never force-push, destructively reset/delete without verified scope and backup, expose secrets, convert runtime data to source, trust an unverified marker, weaken tests, modify Production and GitHub simultaneously without a plan, or declare success before monitoring.
