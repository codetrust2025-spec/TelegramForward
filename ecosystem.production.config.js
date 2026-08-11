/**
 * Production PM2 — backend only, serves built static/ on :8000.
 * No file watch, no Vite dev server.
 *
 *   pm2 start ecosystem.production.config.js
 *   pm2 save
 */
const path = require("path");

// Production runs from an immutable release directory with a `current` symlink:
//
//   /opt/telegramforward/current -> /opt/telegramforward/releases/<sha>
//   /opt/telegramforward/venv                 (shared, NOT inside a release)
//
// Node resolves symlinks, so __dirname here is the *release* directory even
// when this file is loaded through `current`. Deriving both paths from it was
// wrong in two ways at once: the interpreter pointed at a venv that does not
// exist inside a release, so `pm2 start ecosystem.production.config.js` failed to
// boot; and cwd pinned PM2 to today's release, so the next deploy would move
// the symlink while PM2 kept running the old code and reported success.
//
// So: run from the symlink, and take the venv from the deployment root. The
// flat-layout case (no releases/ parent) keeps the original behaviour, which is
// what a local or legacy checkout needs.
const HERE = __dirname;
const IN_RELEASE = path.basename(path.dirname(HERE)) === "releases";
const DEPLOY_ROOT = IN_RELEASE ? path.dirname(path.dirname(HERE)) : HERE;
const ROOT = IN_RELEASE ? path.join(DEPLOY_ROOT, "current") : HERE;
const VENV_PYTHON = path.join(DEPLOY_ROOT, "venv", "bin", "python3");

module.exports = {
  apps: [
    {
      name: "telegram-backend",
      cwd: ROOT,
      script: path.join("scripts", "uvicorn_reload.py"),
      interpreter: VENV_PYTHON,
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
        // Loopback only. nginx is the sole front door — it proxies to
        // 127.0.0.1:8000 — so binding wider published the backend on the host's
        // public IP with no firewall in front of it, letting callers reach the
        // API without passing through the proxy at all.
        HOST: "127.0.0.1",
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
