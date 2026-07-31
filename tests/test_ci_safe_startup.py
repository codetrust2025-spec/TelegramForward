"""Regression coverage for the opt-in side-effect-free CI startup mode."""
from __future__ import annotations

import asyncio
import os
import subprocess
import sys
from pathlib import Path
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

import server


ROOT = Path(__file__).resolve().parents[1]


def test_default_mode_delegates_to_normal_startup_and_shutdown(monkeypatch):
    monkeypatch.delenv("CI_SAFE_STARTUP", raising=False)
    normal_startup = AsyncMock()
    normal_shutdown = AsyncMock()
    with patch.object(server, "_normal_startup", normal_startup), patch.object(
        server, "_normal_shutdown", normal_shutdown
    ):
        asyncio.run(server.startup())
        asyncio.run(server.shutdown())
    normal_startup.assert_awaited_once_with()
    normal_shutdown.assert_awaited_once_with()


def test_ci_safe_mode_skips_all_runtime_orchestration(monkeypatch):
    monkeypatch.setenv("CI_SAFE_STARTUP", "true")
    normal_startup = AsyncMock()
    normal_shutdown = AsyncMock()
    with patch.object(server, "_normal_startup", normal_startup), patch.object(
        server, "_normal_shutdown", normal_shutdown
    ), patch.object(server.telegram_client, "sync_slots") as sync_slots, patch.object(
        server, "_migrate_legacy_files"
    ) as migrate_legacy_files, patch.object(server, "_repair_inbox_conversation_keys") as repair_inbox:
        asyncio.run(server.startup())
        asyncio.run(server.shutdown())
    normal_startup.assert_not_awaited()
    normal_shutdown.assert_not_awaited()
    sync_slots.assert_not_called()
    migrate_legacy_files.assert_not_called()
    repair_inbox.assert_not_called()


def test_ci_safe_mode_serves_health_without_lifespan_side_effects(monkeypatch):
    monkeypatch.setenv("CI_SAFE_STARTUP", "1")
    normal_startup = AsyncMock()
    normal_shutdown = AsyncMock()
    with patch.object(server, "_normal_startup", normal_startup), patch.object(
        server, "_normal_shutdown", normal_shutdown
    ), TestClient(server.app) as client:
        response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
    assert any(route.path == "/health" for route in server.app.routes)
    normal_startup.assert_not_awaited()
    normal_shutdown.assert_not_awaited()


def test_ci_safe_process_imports_server_without_project_dotenv(monkeypatch):
    environment = os.environ.copy()
    environment["CI_SAFE_STARTUP"] = "1"
    environment.pop("DASHBOARD_PASSWORD", None)
    result = subprocess.run(
        [sys.executable, "-c", "import server; assert any(r.path == '/health' for r in server.app.routes)"],
        cwd=ROOT,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
