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
      interpreter: path.join(ROOT, "venv", "bin", "python3"),
      watch: false,
      autorestart: true,
      max_restarts: 30,
      min_uptime: 5000,
      restart_delay: 3000,
      kill_timeout: 20000,
      listen_timeout: 15000,
      env: {
        PYTHONUNBUFFERED: "1",
        PYTHONPATH: "/opt/telegramforward",
        HOST: "0.0.0.0",
        PORT: "8000",
        NO_RELOAD: "1",
        LOG_LEVEL: "info",
        // Company payee UPI handles (all route to J Ravinder's account).
        // Unioned with the payment_upi_id runtime config; add new handles here.
        COMPANY_PAYMENT_UPI_IDS: "raviarvind1111@ybl",
        OCR_ENABLED: "true",
        OLLAMA_BASE_URL: "http://127.0.0.1:11435",
        OLLAMA_REMOTE_ENABLED: "true",
        OLLAMA_EXPECT_REVERSE_SSH_TUNNEL: "true",
        OLLAMA_INFERENCE_HOST_ID: "jagadeesh-ollama",
        // Ollama-assisted mail audit. Read-only second opinion on audit
        // findings; it cannot book, reschedule, cancel, approve, or change a
        // candidate status. Deliberately a separate switch from
        // AI_INTERVIEW_AUTO_BOOKING_ENABLED: turning this off must never
        // affect interview auto-booking, and vice versa.
        AI_MAIL_AUDIT_ENABLED: "true",
        // One review at a time. Audit inference always yields to live Gmail
        // sync and interview booking; this caps what it can take when idle.
        AI_MAIL_AUDIT_CONCURRENCY: "1",
      },
    },
  ],
};
