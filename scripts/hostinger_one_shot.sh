#!/bin/bash
# One-shot Hostinger production update — paste in Browser terminal:
#   curl -fsSL https://raw.githubusercontent.com/codetrust2025-spec/TelegramForward/main/scripts/hostinger_one_shot.sh | bash
set -euo pipefail

echo "=== TelegramForward one-shot production update ==="

if [ "$(id -u)" -ne 0 ]; then
  echo "ERROR: run as root (Hostinger Browser terminal is fine)"
  exit 1
fi

apt-get update -qq
apt-get install -y -qq git curl

OLD="${OLD:-/opt/telegramforward}"
STAMP="$(date +%Y%m%d_%H%M%S)"
BACKUP="/opt/telegramforward_backup_$STAMP"

if [ ! -d "$OLD" ]; then
  echo "No $OLD — fresh install"
  git clone https://github.com/codetrust2025-spec/TelegramForward.git "$OLD"
  cd "$OLD"
  bash deploy.sh
  echo "=== Fresh install complete ==="
  exit 0
fi

echo "[1/4] Backup $OLD -> $BACKUP"
cp -a "$OLD" "$BACKUP"

echo "[2/4] Clone latest from GitHub"
rm -rf /opt/telegramforward_new
git clone https://github.com/codetrust2025-spec/TelegramForward.git /opt/telegramforward_new
mkdir -p /opt/telegramforward_new/data
cp -a "$OLD"/session_*.session* /opt/telegramforward_new/ 2>/dev/null || true
cp -a "$OLD/data"/* /opt/telegramforward_new/data/ 2>/dev/null || true
cp -a "$OLD/groups_list.json" /opt/telegramforward_new/data/ 2>/dev/null || true
cp -a "$OLD/custom_message.txt" /opt/telegramforward_new/data/ 2>/dev/null || true
cp -a "$OLD/.env" /opt/telegramforward_new/ 2>/dev/null || true

echo "[3/4] Swap to new code"
mv "$OLD" "/opt/telegramforward_old_$STAMP"
mv /opt/telegramforward_new "$OLD"

echo "[4/4] Build + restart"
cd "$OLD"
bash scripts/production_update.sh

echo ""
echo "=== ALL DONE ==="
echo "Open: http://187.127.169.159  then Ctrl+Shift+R"
echo "Backup: $BACKUP"
echo "Old code: /opt/telegramforward_old_$STAMP"
