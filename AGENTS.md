# Repository Instructions for AI Engineering Agents

This file applies to the entire repository. It is the mandatory entry point for AI assistants and automated engineering agents.

## Authority

1. Direct user and system instructions take precedence.
2. `PROJECT_RULES.md` is the authoritative repository policy.
3. `DEVELOPMENT_WORKFLOW.md`, `DEPLOYMENT.md`, and `RECOVERY.md` define the required procedures for their activities.
4. `CONTRIBUTING.md` defines contributor expectations.
5. Nested `AGENTS.md` files may add local implementation rules but may not weaken root safety, pull-request/CI, data-protection, backup, or deployment rules.

Stop and report any conflict that could damage data, expose a secret, bypass a required Pull Request or CI check, or modify Production unexpectedly.

## Mandatory workflow

Every change follows:

1. Requirements
2. Feature branch from synchronized `main`
3. Development
4. Backend and frontend tests
5. Commit
6. Push
7. Pull Request
8. Merge the CI-passing Pull Request to `main` (independent review is optional)
9. Backup verification
10. Production deployment from the exact merged commit
11. Verification
12. Monitoring

Do not skip gates because a change appears small.

Continue through these gates automatically. Do not stop after step 7 or step 8
to ask whether to proceed when deployment is permitted. `PROJECT_RULES.md`
defines the definition of done, the continuous delivery obligation, and the only
legitimate blockers; follow it rather than pausing for routine confirmation.

When genuinely blocked, report the blocker and what is needed to clear it, then
continue from that point once it is resolved.

## Required preflight

Before editing:

```bash
git status --short --branch
git fetch origin main
git rev-parse main
git rev-parse origin/main
```

- Preserve dirty work before changing branches; never discard user changes.
- Never develop on `main`.
- Create a focused branch from clean, synchronized `main`.
- Use `codex/` for Codex-created branches unless the user specifies another valid name.
- Read applicable manuals and nested `AGENTS.md` files.

## Engineering rules

- Fix root causes and avoid unjustified compatibility layers.
- Keep changes focused, reviewable, and consistent with current architecture.
- Do not silently change business behavior or fix unrelated defects.
- Add regression tests for changed behavior; never weaken tests to make them pass.
- Keep API routes thin and business logic in the appropriate domain module.
- Preserve account isolation and the booking/payment invariants in `PROJECT_RULES.md`.
- Update manuals when architecture, workflow, dependencies, deployment, recovery, or ownership changes.

## Validation

Run focused tests first, then the complete affected suites:

```bash
python -m pytest -q tests
cd dashboard
npm ci
npm test
npm run build
```

Before commit, run `git diff --check`, inspect the staged file list, scan staged content for secrets, and verify no runtime data is included. Run relevant Gradle tests when Android code changes.

## Protected data

Never print, commit, overwrite, delete, or package:

- `.env`, passwords, keys, tokens, or credentials
- uploads, resumes, payment proofs, or interview evidence
- PostgreSQL or other database contents
- Telegram session files
- runtime JSON/state, queues, worker state, logs, or caches
- backups, rollback archives, or forensic evidence

Templates contain placeholders or safe defaults only. Production values must not appear in commands, logs, fixtures, screenshots, commits, PRs, or reports.

## Git prohibitions

- Never commit or push directly on `main`.
- Never force-push or rewrite shared history.
- Never use destructive cleanup/reset commands on unverified paths.
- Never deploy a dirty tree, local patch, or unmerged branch.
- Never claim a marker is authoritative unless it matches the running release and GitHub `main`.

GitHub `main` is protected. Every change must use a Pull Request and pass the required `Backend tests` and `Frontend tests` checks before merge. Independent approval is optional for this single-owner repository. If review occurs, resolve its conversations before merge. Never attempt to bypass, weaken, or temporarily disable the Pull Request or required-check protections.

## Production prohibitions

- Never deploy without explicit authorization and a verified, restorable backup.
- Never deploy from a developer working directory.
- Never use legacy SCP or single-file hotfix scripts for routine deployment.
- Never overwrite protected runtime paths or edit active source in place.
- Stop after failed health, manifest, asset, database, or rollback checks.

Use only `DEPLOYMENT.md` for releases and `RECOVERY.md` for incidents or drift.

## Completion report

Report the branch/commit, changed behavior and files, tests/builds, known baseline failures, security/runtime scans, remaining risks, and whether anything was pushed, merged, deployed, restarted, or changed in Production.

If the change reached Production, include the merge commit, the deployed commit,
proof that local `main`, GitHub `main`, and the deployed commit match, the
Production verification performed, and the rollback target retained. If it did
not, say which gate it stopped at and why.
