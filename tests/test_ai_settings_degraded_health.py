"""The AI settings endpoint must survive a missing Karthik playbook tree.

``core.ai_smart_reply`` imports ``core.karthik.*``, which is deliberately kept
outside git. Deployments without that tree cannot import the module, and the
settings endpoint used to propagate the ImportError as a 500 — which blanked
the entire admin AI screen, including the unrelated global OCR switch.
"""

from __future__ import annotations

import builtins
import importlib
import sys

import pytest


@pytest.fixture()
def ai_router():
    # api.routers.ai imports from server, which in turn mounts this router, so
    # the app module has to be initialised first or the import cycles.
    importlib.import_module("server")
    return importlib.import_module("api.routers.ai")


def _block_smart_reply(monkeypatch):
    """Make `from core import ai_smart_reply` fail the way production does."""
    monkeypatch.delitem(sys.modules, "core.ai_smart_reply", raising=False)
    real_import = builtins.__import__

    def fake_import(name, globals=None, locals=None, fromlist=(), level=0):
        if name == "core" and fromlist and "ai_smart_reply" in fromlist:
            raise ModuleNotFoundError("No module named 'core.karthik'")
        if name.startswith("core.ai_smart_reply") and not name.startswith(
            "core.ai_smart_reply_store"
        ):
            raise ModuleNotFoundError("No module named 'core.karthik'")
        return real_import(name, globals, locals, fromlist, level)

    monkeypatch.setattr(builtins, "__import__", fake_import)


def test_health_degrades_instead_of_raising(ai_router, monkeypatch):
    _block_smart_reply(monkeypatch)

    health = ai_router._smart_reply_health()

    assert health["available"] is False
    assert health["enabled"] is False
    assert "unavailable_reason" in health
    # The settings screen keys its "API key missing" banner off this field, so
    # it has to be present and truthful even in the degraded shape.
    assert isinstance(health["api_key_present"], bool)


def test_degraded_health_reports_the_api_key_from_the_environment(
    ai_router, monkeypatch
):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setenv("AI_API_KEY", "sk-present")
    _block_smart_reply(monkeypatch)

    assert ai_router._smart_reply_health()["api_key_present"] is True

    monkeypatch.setenv("AI_API_KEY", "   ")
    assert ai_router._smart_reply_health()["api_key_present"] is False


def test_health_marks_available_when_the_module_imports(ai_router, monkeypatch):
    stub = type("Stub", (), {"health": staticmethod(lambda: {"enabled": True})})()
    monkeypatch.setitem(sys.modules, "core.ai_smart_reply", stub)

    health = ai_router._smart_reply_health()

    assert health["available"] is True
    assert health["enabled"] is True


def test_health_does_not_override_an_explicit_available_flag(ai_router, monkeypatch):
    stub = type(
        "Stub", (), {"health": staticmethod(lambda: {"available": False, "enabled": False})}
    )()
    monkeypatch.setitem(sys.modules, "core.ai_smart_reply", stub)

    assert ai_router._smart_reply_health()["available"] is False


def test_config_endpoint_does_not_import_the_engine_at_module_scope(ai_router):
    """The route body must not hard-import ai_smart_reply any more."""
    import inspect

    src = inspect.getsource(ai_router.ai_smart_reply_get_config)
    assert "from core import ai_smart_reply" not in src
    assert "_smart_reply_health()" in src

    src_post = inspect.getsource(ai_router.ai_smart_reply_update_config)
    assert "from core import ai_smart_reply" not in src_post
    assert "_smart_reply_health()" in src_post
