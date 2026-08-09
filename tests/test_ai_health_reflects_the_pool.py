"""The AI availability gate must answer for the pool, not just the primary.

Invite extraction refuses to run when `health()` says no. Judging the
configured primary alone turned a *degraded* primary into a *total* outage:
rtx4060 was made primary carrying the vision model but not the text one, and
every invite read reported "The AI model is unavailable" while jagadeesh was
sitting there able to serve it.
"""

import pytest

from core import ai_gateway, ollama_nodes
from core.ai_gateway import AIGatewayError

TEXT = "qwen2.5:7b"
VISION = "qwen3-vl:8b-instruct"


@pytest.fixture(autouse=True)
def isolated(monkeypatch, tmp_path):
    monkeypatch.setenv("OLLAMA_NODE_STATE_FILE", str(tmp_path / "state.json"))
    for name in ("OLLAMA_PRIMARY_NODE", "OLLAMA_BASE_URL", "OLLAMA_ENABLE_VPS_LOCAL"):
        monkeypatch.delenv(name, raising=False)
    ollama_nodes.reset_breakers()
    yield
    ollama_nodes.reset_breakers()


def _pool(monkeypatch, inventory):
    """node -> set of models it carries. Absent from the dict means offline."""

    def fake_health(node_id, *, model, timeout=5, deep=True):
        models = inventory.get(node_id)
        reachable = models is not None
        return {
            "id": node_id, "label": node_id,
            "primary": node_id == ollama_nodes.primary_node_id(),
            "status": "online" if reachable else "offline",
            "endpoint_reachable": reachable,
            "model": model,
            "model_available": bool(models and model in models),
            "model_loaded": False, "response_time_ms": 5, "error": None,
            "installed_models": sorted(models or []),
            "breaker": ollama_nodes.breaker_state(node_id),
            "available": reachable,
        }

    monkeypatch.setattr(ollama_nodes, "node_health", fake_health)

    def fake_request(path, **kwargs):
        base = kwargs.get("base_url") or ""
        node_id = next(
            (n["id"] for n in ollama_nodes.configured_nodes() if n["base_url"] == base),
            None,
        )
        models = inventory.get(node_id)
        if models is None:
            # What the real transport raises; health() only handles this type.
            raise AIGatewayError(
                "connection refused", code="OLLAMA_CONNECTION_FAILED"
            )
        return {"models": [{"name": name} for name in sorted(models)]}

    monkeypatch.setattr(ai_gateway, "_request_json", fake_request)


def test_a_primary_missing_the_model_does_not_read_as_a_total_outage(monkeypatch):
    """The exact production failure."""
    _pool(monkeypatch, {"rtx4060": {VISION}, "jagadeesh": {TEXT, VISION}})
    ollama_nodes.set_primary_node("rtx4060", force=True)

    result = ai_gateway.health(model=TEXT)

    assert result["model_available"] is True, (
        "jagadeesh can serve this model, so the gate must not report an outage"
    )


def test_vision_still_reports_against_the_fast_primary(monkeypatch):
    _pool(monkeypatch, {"rtx4060": {VISION}, "jagadeesh": {TEXT, VISION}})
    ollama_nodes.set_primary_node("rtx4060", force=True)
    assert ai_gateway.health(model=VISION)["model_available"] is True


def test_a_genuine_outage_is_still_reported(monkeypatch):
    """The relaxation must not hide a pool that truly cannot serve."""
    _pool(monkeypatch, {"rtx4060": {VISION}, "jagadeesh": {VISION}})
    ollama_nodes.set_primary_node("rtx4060", force=True)

    result = ai_gateway.health(model=TEXT)

    assert result["model_available"] is False
    assert result["error_code"] == "OLLAMA_MODEL_NOT_FOUND"


def test_every_node_offline_is_still_reported(monkeypatch):
    _pool(monkeypatch, {})
    ollama_nodes.set_primary_node("jagadeesh", force=True)
    assert ai_gateway.health(model=TEXT)["endpoint_reachable"] is False


def test_an_explicit_node_is_still_answered_for_that_node(monkeypatch):
    """The admin screen asks per node and must keep getting the truth about it,
    not a pool-wide answer that hides which machine is short of a model."""
    _pool(monkeypatch, {"rtx4060": {VISION}, "jagadeesh": {TEXT, VISION}})
    ollama_nodes.set_primary_node("jagadeesh", force=True)

    assert ai_gateway.health(model=TEXT, node_id="rtx4060")["model_available"] is False
    assert ai_gateway.health(model=TEXT, node_id="jagadeesh")["model_available"] is True
