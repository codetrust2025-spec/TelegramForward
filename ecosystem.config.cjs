/**
 * PM2 — auto-restart on code change (production-style, no manual restart).
 *
 * Backend: full process restart when Python source changes (watch: true).
 * Frontend: Vite dev with PM2 watch on dashboard/src.
 *
 *   npm install -g pm2
 *   pm2 start ecosystem.config.cjs
 *   pm2 logs
 *
 * For in-process uvicorn reload instead of PM2 watch:
 *   set PM2_FILE_WATCH=0  (uses uvicorn --reload inside the process)
 */

const path = require("path");
const ROOT = __dirname;

const PM2_FILE_WATCH = process.env.PM2_FILE_WATCH !== "0";
const RELOAD_DELAY_MS = Math.max(500, parseInt(process.env.RELOAD_DELAY || "1500", 10));

const PYTHON_WATCH = PM2_FILE_WATCH
  ? ["core", "features", "workers", "services", "scripts", "server.py", "run.py"]
  : false;

module.exports = {
  apps: [
    {
      name: "telegram-backend",
      cwd: ROOT,
      script: path.join("scripts", "uvicorn_reload.py"),
      interpreter: "python",
      watch: PYTHON_WATCH,
      watch_delay: RELOAD_DELAY_MS,
      ignore_watch: [
        "node_modules",
        "data",
        "data/**",
        "static",
        "dashboard",
        "__pycache__",
        ".git",
        ".cursor",
        "logs",
        "logs/**",
        "*.session",
        "*.session-shm",
        "*.session-wal",
        "*.session-journal",
        "*.log",
        "reload.log",
        ".running_workers.json",
        ".restart_count.json",
      ],
      autorestart: true,
      max_restarts: 30,
      min_uptime: 2000,
      restart_delay: RELOAD_DELAY_MS,
      kill_timeout: 15000,
      listen_timeout: 10000,
      shutdown_with_message: true,
      env: {
        PYTHONUNBUFFERED: "1",
        HOST: "127.0.0.1",
        PORT: "8000",
        RELOAD_DELAY: String(RELOAD_DELAY_MS / 1000),
        // PM2 restarts whole process on file change; disable uvicorn double-watch
        NO_RELOAD: PM2_FILE_WATCH ? "1" : "",
      },
    },
    {
      name: "telegram-dashboard",
      cwd: path.join(ROOT, "dashboard"),
      script: "npm",
      args: "run dev",
      interpreter: "none",
      watch: ["src", "vite.config.js", "vite.config.ts", "index.html"],
      watch_delay: RELOAD_DELAY_MS,
      ignore_watch: ["node_modules", "dist"],
      autorestart: true,
      max_restarts: 20,
      min_uptime: 2000,
      restart_delay: RELOAD_DELAY_MS,
      env: {
        BROWSER: "none",
      },
    },
  ],
};
