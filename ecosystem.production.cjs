/**
 * Production PM2 — backend only, serves built static/ on :8000.
 * No file watch, no Vite dev server.
 *
 *   pm2 start ecosystem.production.cjs
 *   pm2 save
 */
const path = require("path");
const ROOT = __dirname;

module.exports = {
  apps: [
    {
      name: "telegram-backend",
      cwd: ROOT,
      script: path.join("scripts", "uvicorn_reload.py"),
      interpreter: "python3",
      watch: false,
      autorestart: true,
      max_restarts: 30,
      min_uptime: 5000,
      restart_delay: 3000,
      kill_timeout: 20000,
      listen_timeout: 15000,
      env: {
        PYTHONUNBUFFERED: "1",
        HOST: "0.0.0.0",
        PORT: "8000",
        NO_RELOAD: "1",
        LOG_LEVEL: "info",
      },
    },
  ],
};
