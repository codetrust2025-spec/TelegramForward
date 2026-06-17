# Git ↔ Production sync

Production drift happened because **two conflicting workflows** were used at the same time.

## Why git fell behind prod

| Problem | What happened |
|--------|----------------|
| **SCP deploy scripts** | 100+ `scripts/_vps_deploy_*.py` files upload single files via SSH, **never committing to git**. |
| **No git on VPS** | `/opt/telegramforward` was not a git repo, so `git pull` in `production_update.sh` was skipped. |
| **VPS edits** | `server.py` and `dashboard/src/*` were patched directly on the server. |
| **Stale static in git** | A build was deployed to prod but the matching `static/assets/app-*.js` was not committed. |
| **`data/` gitignored** | Correct for secrets — but team must know live data never comes from git. |

## Permanent rule

> **GitHub `main` is the only source of truth. Prod only changes via `deploy_prod.py`.**

Do **not** use `scripts/_vps_deploy_*.py` for routine updates (emergency hotfix only — then commit immediately).

## One-time VPS setup (optional)

The GitHub repo is **private**, so the VPS cannot `git pull` without a deploy key.
`deploy_prod.py` uploads all git-tracked files via SFTP instead — no VPS git setup required.

Optional (public mirror or deploy key):

```powershell
python scripts/setup_vps_git.py
```

## Every production deploy

```powershell
$env:VPS_PASSWORD = 'your-vps-password'
python scripts/deploy_prod.py
```

This script:

1. Bumps `BUILD_STAMP` in `dashboard/src/config.js` (cache bust)
2. Runs `npm run build` locally
3. Writes `static/production.manifest.json` (commit + bundle hashes)
4. Commits and pushes to GitHub
5. Uploads **all git-tracked files** + `static/` to VPS (SFTP — works with private GitHub)
6. Writes `.deploy-commit` on VPS (commit pin for verification)
7. Restarts `telegram-backend`
8. Runs `verify_git_prod_sync.py`

Options:

- `--skip-build` — deploy existing `static/`
- `--skip-push` — deploy current HEAD without pushing (only if already pushed)
- `--no-commit` — skip auto-commit (not recommended)

**Private repo:** VPS uses `.deploy-commit` marker + file hashes, not `git pull`.

## Verify sync (any time)

```powershell
$env:VPS_PASSWORD = 'your-vps-password'
python scripts/verify_git_prod_sync.py
```

Exit code `0` = git, live site, and VPS match.

## Team workflow

```text
edit code locally → test → deploy_prod.py → teammates git pull
```

Clone for new devs:

```bash
git clone https://github.com/codetrust2025-spec/TelegramForward.git
```

## What stays out of git

- `.env` — API keys (use `.env.example`)
- `data/` — sessions, candidates, credentials vault
- `config/dashboard_handlers.yaml` — handler passwords

Copy these from VPS backup or admin when onboarding.

## Rollback

```bash
# On VPS
cd /opt/telegramforward
git fetch origin main
git checkout main
git reset --hard <previous-commit>
pm2 restart telegram-backend
```

Or redeploy an older commit from your PC:

```powershell
git checkout <sha>
python scripts/deploy_prod.py
git checkout main
```

## Files

| Script | Purpose |
|--------|---------|
| `scripts/deploy_prod.py` | **Only** routine prod deploy |
| `scripts/setup_vps_git.py` | One-time VPS git init |
| `scripts/verify_git_prod_sync.py` | Drift detector |
| `scripts/write_production_manifest.py` | Update manifest only |
| `scripts/cleanup_static_assets.py` | Remove old `app-*.js` / `index-*.css` backups (VPS + local) |
| `scripts/production_update.sh` | VPS-side build (used by hostinger_one_shot; prefer deploy_prod) |

### Clean old bundle backups

After many deploys, `static/assets/` can accumulate hundreds of stale Vite chunks. Safe cleanup:

```powershell
python scripts/cleanup_static_assets.py --all          # dry-run
python scripts/cleanup_static_assets.py --all --execute
```

Keeps only files referenced in `static/index.html` / `production.manifest.json`.
