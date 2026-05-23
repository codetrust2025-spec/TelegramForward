#!/bin/bash
# ─────────────────────────────────────────────────────────────
# Safe production update — pull latest code without losing data.
#
# Run ON THE VPS (as root or deploy user):
#   cd /opt/telegramforward   # or your install path
#   bash scripts/production_update.sh
#
# Preserves: data/, *.session, groups list, account state.
# Updates: Python deps, dashboard build, PM2 backend restart.
# ─────────────────────────────────────────────────────────────

set -euo pipefail

PROJECT_DIR="${PROJECT_DIR:-$(cd "$(dirname "$0")/.." && pwd)}"
cd "$PROJECT_DIR"

STAMP="$(date +%Y%m%d_%H%M%S)"
BACKUP_DIR="$PROJECT_DIR/backups/pre_update_$STAMP"
PORT="${PORT:-8000}"
HEALTH_URL="http://127.0.0.1:${PORT}/health"

echo "=== TelegramForward — production update ==="
echo "Project: $PROJECT_DIR"
echo "Backup:  $BACKUP_DIR"
echo ""

# ── 1. Graceful stop ─────────────────────────────────────────
echo "[1/7] Stopping workers and backend..."
if curl -sf -m 5 "$HEALTH_URL" >/dev/null 2>&1; then
  curl -sf -m 15 -X POST "http://127.0.0.1:${PORT}/stop" >/dev/null 2>&1 || true
  sleep 3
fi
pm2 stop telegram-backend 2>/dev/null || true
pm2 stop telegramforward 2>/dev/null || true
pm2 stop telegram-dashboard 2>/dev/null || true
sleep 2

# ── 2. Backup runtime data ───────────────────────────────────
echo "[2/7] Backing up data and sessions..."
mkdir -p "$BACKUP_DIR"
if [ -d "$PROJECT_DIR/data" ]; then
  cp -a "$PROJECT_DIR/data" "$BACKUP_DIR/data"
fi
shopt -s nullglob
for f in "$PROJECT_DIR"/session_*.session*; do
  cp -a "$f" "$BACKUP_DIR/" 2>/dev/null || true
done
shopt -u nullglob
if [ -f "$PROJECT_DIR/.env" ]; then
  cp -a "$PROJECT_DIR/.env" "$BACKUP_DIR/.env"
fi
echo "      Backup saved to $BACKUP_DIR"

# ── 3. Pull latest code (skip if uploaded directly, no .git) ─
echo "[3/7] Updating code..."
if [ -d "$PROJECT_DIR/.git" ]; then
  git fetch origin main
  git pull origin main
else
  echo "      Skipping git pull — using code already on disk"
fi

# ── 4. Python deps ───────────────────────────────────────────
echo "[4/7] Installing Python dependencies..."
if [ -d "$PROJECT_DIR/venv" ]; then
  # shellcheck disable=SC1091
  source "$PROJECT_DIR/venv/bin/activate"
elif [ -d "$PROJECT_DIR/.venv" ]; then
  # shellcheck disable=SC1091
  source "$PROJECT_DIR/.venv/bin/activate"
else
  python3 -m venv "$PROJECT_DIR/venv"
  # shellcheck disable=SC1091
  source "$PROJECT_DIR/venv/bin/activate"
fi
pip install -q -r requirements.txt

# ── 5. Build dashboard → static/ ─────────────────────────────
echo "[5/7] Building dashboard..."
cd "$PROJECT_DIR/dashboard"
npm install --silent
npm run build
cd "$PROJECT_DIR"

if [ ! -f "$PROJECT_DIR/static/index.html" ]; then
  echo "ERROR: dashboard build failed — static/index.html missing"
  exit 1
fi

# ── 6. Restart PM2 (production config) ───────────────────────
echo "[6/7] Starting backend (production mode)..."
pm2 delete telegram-dashboard 2>/dev/null || true
pm2 delete telegramforward 2>/dev/null || true
pm2 delete telegram-backend 2>/dev/null || true
pm2 delete ecosystem.production 2>/dev/null || true
PYTHON_BIN="$PROJECT_DIR/venv/bin/python"
if [ ! -x "$PYTHON_BIN" ]; then
  PYTHON_BIN="$(command -v python3)"
fi
cd "$PROJECT_DIR"
HOST=0.0.0.0 PORT="$PORT" NO_RELOAD=1 PYTHONUNBUFFERED=1 \
  pm2 start scripts/uvicorn_reload.py --name telegram-backend --interpreter "$PYTHON_BIN"
pm2 save

# ── 7. Health check ────────────────────────────────────────────
echo "[7/7] Waiting for health check..."
ok=0
for i in $(seq 1 30); do
  if curl -sf -m 3 "$HEALTH_URL" >/dev/null 2>&1; then
    ok=1
    break
  fi
  sleep 1
done

echo ""
if [ "$ok" -eq 1 ]; then
  echo "=== Update complete ==="
  echo "Dashboard: http://$(curl -s ifconfig.me 2>/dev/null || echo 'YOUR_SERVER_IP')"
  echo "Backup:    $BACKUP_DIR"
  echo ""
  echo "Next steps:"
  echo "  1. Hard-refresh browser (Ctrl+Shift+R)"
  echo "  2. Log in accounts if needed (account_info may need refresh)"
  echo "  3. pm2 logs telegram-backend — tail logs"
  echo "  4. Start workers from dashboard when ready"
else
  echo "WARNING: Backend did not respond on $HEALTH_URL"
  echo "Check: pm2 logs telegram-backend"
  exit 1
fi
