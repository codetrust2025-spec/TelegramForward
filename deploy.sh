#!/bin/bash
# ─────────────────────────────────────────────────────────────
# Telegram Forwarder — VPS Deployment Script
# Run this on your VPS after uploading the project files
# Usage: bash deploy.sh
# ─────────────────────────────────────────────────────────────

set -e

echo "=== Telegram Forwarder Deployment ==="

# 1. System packages
echo "[1/6] Installing system packages..."
apt-get update -qq
apt-get install -y python3 python3-pip python3-venv nodejs npm nginx -qq

# 2. Python virtual environment
echo "[2/6] Setting up Python environment..."
cd /opt/telegramforward
python3 -m venv venv
source venv/bin/activate
pip install -q -r requirements.txt

# 3. Build React frontend
echo "[3/6] Building frontend..."
cd dashboard
npm install --silent
npm run build
cd ..

# 4. PM2 — production backend only (built static/, no dev server)
echo "[4/6] Setting up PM2 (production)..."
npm install -g pm2 --silent
pm2 delete all 2>/dev/null || true
# HOST deliberately not set here: the ecosystem config binds 127.0.0.1 so nginx
# is the only way in. A shell prefix would have overridden it.
PORT=8000 NO_RELOAD=1 pm2 start ecosystem.production.config.js
pm2 save
pm2 startup | tail -1 | bash

# 5. Nginx config
echo "[5/6] Configuring Nginx..."
cat > /etc/nginx/sites-available/telegramforward << 'NGINX'
server {
    listen 80;
    server_name _;

    # Increase timeouts for WebSocket
    proxy_read_timeout 3600;
    proxy_send_timeout 3600;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_cache_bypass $http_upgrade;
    }
}
NGINX

ln -sf /etc/nginx/sites-available/telegramforward /etc/nginx/sites-enabled/
rm -f /etc/nginx/sites-enabled/default
nginx -t && systemctl reload nginx

echo ""
echo "=== Deployment Complete ==="
echo "Dashboard: http://$(curl -s ifconfig.me)"
echo ""
echo "Useful commands:"
echo "  pm2 logs telegram-backend      — view live logs"
echo "  pm2 restart telegram-backend   — restart server"
echo "  pm2 stop telegram-backend      — stop server"
echo "  bash scripts/production_update.sh — safe git pull + rebuild"
