# Production Deployment Manual

This is the authoritative Production deployment policy. Legacy guides and scripts may describe historical workflows; they do not authorize deployment.

## Principles

- Production is built only from committed, Pull-Request-merged, CI-validated GitHub `main` code.
- The deployed commit exactly equals `origin/main`.
- Builds occur in a disposable clean checkout, never a developer worktree.
- Releases are immutable and stored in versioned directories.
- Runtime data lives outside releases.
- `current` is the only active pointer and switches atomically.
- A verified previous release remains available for rollback.
- A verified, restorable backup is mandatory before deployment.
- Deployment is incomplete until verification and monitoring pass.

## Forbidden paths

Do not use a process that uploads a developer worktree, includes dirty/untracked files, commits during deployment, pushes directly to `main`, uploads selected files as a routine release, edits Production source, overwrites the active directory, mixes obsolete files into a release, changes protected runtime data, or writes a marker before verification.

`scripts/deploy_prod.py`, `deploy.sh`, and one-off `_deploy*` or `vps_deploy*` scripts are legacy tools and are not approved for routine Production deployment under this policy.

## Required layout

```text
/opt/telegramforward/
├── current -> releases/<full-git-commit>/
├── releases/<full-git-commit>/
├── releases/<previous-full-git-commit>/
├── .env
├── data/
├── uploads/                  # when configured separately
├── venv/                     # only when compatibility is verified
└── session_*.session

/var/log/telegramforward/
/var/log/telegramforward-deployments/
/var/backups/telegramforward/<timestamp>-pre-<commit>/
```

Each release links to required protected runtime paths; it never contains copies of their contents.

## Authorization

The change owner prepares the Pull Request and validates behavior and rollback; independent review is optional for this single-owner repository. The release operator verifies backup and deployment evidence, and the incident owner decides rollback. Pull Request merge is not deployment approval.

## Pre-deployment gate

All items must pass:

1. Explicit deployment authorization exists.
2. Local `main` is clean and equals `origin/main`.
3. The target is the Pull-Request-merged commit on `origin/main`.
4. GitHub branch protection was satisfied, including passing `Backend tests` and `Frontend tests` checks on the merged change. Independent review is optional.
5. Backend tests, frontend tests/build, and Python import/compile checks passed for the exact release artifact.
6. Secret and runtime-data scans passed.
7. The artifact was built from a clean checkout of the exact commit.
8. Its manifest records commit, release ID, timestamp, operator, build hash, package hash, and critical file hashes.
9. The previous release is identifiable and healthy.
10. A backup outside `/opt/telegramforward` was created and verified.
11. Rollback commands and the responsible operator are known.

Python lockfiles must be generated and verified on the target Linux platform. If they are absent, dependency reproducibility remains an explicit release blocker or documented risk. Frontend installs use `dashboard/package-lock.json` with `npm ci`.

## Backup requirements

Back up PostgreSQL custom-format and schema dumps, `.env`/runtime configuration under access control, uploads/evidence, sessions/state, required runtime JSON/queues, Nginx/PM2 configuration, and the current commit/manifest. Include an inventory and checksums.

Verification includes:

```bash
sha256sum -c SHA256SUMS
pg_restore --list teleautomation.dump
```

Inspect archive listings and confirm the backup is outside the active application directory. Existence alone is not verification.

## Build and release preparation

1. Resolve the full target commit from `origin/main`.
2. Create a disposable detached worktree or Git archive.
3. Install dependencies with approved locks/tool versions.
4. Run backend/frontend tests and build assets.
5. Generate `static/production.manifest.json`.
6. Calculate SHA-256 hashes for package, server entry point, manifest, JS, CSS, and other critical assets.
7. Package only allowlisted source, migrations, templates, scripts, and built assets.
8. Exclude all protected runtime paths.

## Release installation

Upload to a temporary path, verify hashes on Production, extract to `/opt/telegramforward/releases/<commit>/`, set least-privilege permissions, link protected runtime paths, and run offline compile/import and manifest checks. Do not point `current` to an unverified release.

## Atomic switch

The deployment tool creates a new symlink and atomically renames it over `/opt/telegramforward/current`. Nginx static root and asset alias both resolve through `current/static`. PM2 runs with `cwd=/opt/telegramforward/current` and the protected Production environment.

The switch is guarded by automatic restoration of the previous symlink and service state on any failed critical gate.

## Post-switch verification

Before writing the final marker, verify:

- `current` resolves to the target commit directory;
- PM2 reports `telegram-backend` online with the expected working directory;
- Nginx validates and serves the current index and assets;
- local and public `/health` succeed;
- public index and JS/CSS hashes match the release;
- Python startup and integrations have no new critical errors;
- `POST /bookings/confirm` exists and rejects invalid input without creating records;
- the retired legacy booking endpoint returns HTTP 410;
- protected runtime paths still resolve outside the release.

Only then write the deployed-commit marker and healthy deployment record atomically.

## Rollback

On critical failure: atomically repoint `current` to the verified previous release, restart PM2 with the protected environment, reload Nginx if needed, verify health/assets/manifest, restore the previous marker, and record timestamp, releases, operator, reason, and results.

A failed rollback is a hard incident; stop and follow `RECOVERY.md`.

## Monitoring

Monitor PM2 status/restarts, Nginx errors, database connectivity, booking/payment errors, duplicate records, worker/queue/integration health, latency, and public health for the agreed period. Record proof that:

```text
Local main == GitHub main == Production marker == Production manifest
```
