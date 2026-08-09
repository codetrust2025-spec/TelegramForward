"""The three-laptop inference pool: membership, failover, and recovery.

The pool is reached over reverse SSH tunnels from laptops, so nodes disappear
routinely — a closed lid is an outage. Routing has to survive that without
either hammering a dead node or moving production's configured primary every
time a probe times out.
"""

import json

import pytest

from core import ollama_nodes

MODEL = "qwen3-vl:8b-instruct"


@pytest.fixture(autouse=True)
def isolated(monkeypatch, tmp_path):
    monkeypatch.setenv("OLLAMA_NODE_STATE_FILE", str(tmp_path / "state.json"))
    for name in (
        "OLLAMA_PRIMARY_NODE",
        "OLLAMA_BASE_URL",
        "OLLAMA_NODE_RTX4060_URL",
        "OLLAMA_NODE_JAGADEESH_URL",
        "OLLAMA_NODE_OUR_MACHINE_URL",
        "OLLAMA_ENABLE_VPS_LOCAL",
        "OLLAMA_NODE_FAILURE_THRESHOLD",
        "OLLAMA_NODE_COOLDOWN_SECONDS",
    ):
        monkeypatch.delenv(name, raising=False)
    ollama_nodes.reset_breakers()
    yield
    ollama_nodes.reset_breakers()


def _stub_health(monkeypatch, healthy: set[str]):
    """Every node reachable with the model, except those left out of `healthy`."""

    def fake(node_id, *, model, timeout=5, deep=True):
        ok = node_id in healthy
        return {
            "id": node_id,
            "label": node_id,
            "primary": node_id == ollama_nodes.primary_node_id(),
            "status": "online" if ok else "offline",
            "endpoint_reachable": ok,
            "model": model,
            "model_available": ok,
            "model_loaded": False,
            "response_time_ms": 5,
            "error": None if ok else "ConnectionRefusedError",
            "breaker": ollama_nodes.breaker_state(node_id),
            "available": ok,
        }

    monkeypatch.setattr(ollama_nodes, "node_health", fake)


# ── pool membership ─────────────────────────────────────────────────────────


def test_the_three_laptops_are_present_in_preference_order():
    ids = [n["id"] for n in ollama_nodes.configured_nodes()]
    assert ids == ["rtx4060", "jagadeesh", "our_machine"]


def test_endpoints_match_the_agreed_tunnel_ports():
    urls = {n["id"]: n["base_url"] for n in ollama_nodes.configured_nodes()}
    assert urls["rtx4060"] == "http://127.0.0.1:11437"
    assert urls["jagadeesh"] == "http://127.0.0.1:11435"
    assert urls["our_machine"] == "http://127.0.0.1:11436"


def test_praveens_node_keeps_its_persisted_id_while_showing_a_clearer_label():
    """Renaming the id would orphan the persisted primary and the admin API."""
    node = ollama_nodes.node("our_machine")
    assert node["id"] == "our_machine"
    assert node["label"] == "Praveen"


def test_the_vps_node_is_absent_unless_explicitly_enabled(monkeypatch):
    assert "vps_local" not in [n["id"] for n in ollama_nodes.configured_nodes()]
    monkeypatch.setenv("OLLAMA_ENABLE_VPS_LOCAL", "true")
    nodes = [n["id"] for n in ollama_nodes.configured_nodes()]
    assert nodes == ["rtx4060", "jagadeesh", "our_machine", "vps_local"]
    assert ollama_nodes.base_url_for("vps_local") == "http://127.0.0.1:11434"


def test_an_existing_jagadeesh_override_still_wins(monkeypatch):
    monkeypatch.setenv("OLLAMA_BASE_URL", "http://127.0.0.1:19999")
    assert ollama_nodes.base_url_for("jagadeesh") == "http://127.0.0.1:19999"
    # ...and must not leak into the new node.
    assert ollama_nodes.base_url_for("rtx4060") == "http://127.0.0.1:11437"


# ── persistence ─────────────────────────────────────────────────────────────


def test_a_chosen_primary_survives_a_restart(monkeypatch, tmp_path):
    ollama_nodes.set_primary_node("our_machine", force=True)
    saved = json.loads((tmp_path / "state.json").read_text(encoding="utf-8"))
    assert saved["primary_node"] == "our_machine"
    # A new process reads the file rather than the code default.
    assert ollama_nodes.primary_node_id() == "our_machine"


def test_an_unknown_persisted_primary_falls_back_instead_of_crashing(tmp_path):
    (tmp_path / "state.json").write_text(
        json.dumps({"primary_node": "a-node-that-was-removed"}), encoding="utf-8"
    )
    assert ollama_nodes.primary_node_id() == "jagadeesh"


def test_selecting_an_unknown_node_is_refused():
    with pytest.raises(ValueError):
        ollama_nodes.set_primary_node("nonsense", force=True)


# ── failover ────────────────────────────────────────────────────────────────


def test_requests_go_to_the_primary_while_it_is_healthy(monkeypatch):
    ollama_nodes.set_primary_node("jagadeesh", force=True)
    _stub_health(monkeypatch, {"jagadeesh", "our_machine"})
    assert ollama_nodes.select_available_node(model=MODEL)["node_id"] == "jagadeesh"


def test_an_unhealthy_primary_fails_over_to_the_next_node(monkeypatch):
    ollama_nodes.set_primary_node("rtx4060", force=True)
    _stub_health(monkeypatch, {"jagadeesh", "our_machine"})
    chosen = ollama_nodes.select_available_node(model=MODEL)
    assert chosen["node_id"] == "jagadeesh"
    assert chosen["was_primary"] is False


def test_a_second_failure_falls_through_to_the_third_node(monkeypatch):
    ollama_nodes.set_primary_node("rtx4060", force=True)
    _stub_health(monkeypatch, {"our_machine"})
    assert ollama_nodes.select_available_node(model=MODEL)["node_id"] == "our_machine"


def test_a_node_missing_the_model_is_not_selected(monkeypatch):
    """An open port is not health. A node can accept TCP and still be useless."""
    ollama_nodes.set_primary_node("jagadeesh", force=True)

    def fake(node_id, *, model, timeout=5, deep=True):
        return {
            "id": node_id, "label": node_id, "primary": False, "status": "degraded",
            "endpoint_reachable": True,
            "model_available": node_id == "our_machine",
            "model_loaded": False, "response_time_ms": 5, "error": None,
            "breaker": ollama_nodes.breaker_state(node_id), "available": False,
        }

    monkeypatch.setattr(ollama_nodes, "node_health", fake)
    assert ollama_nodes.select_available_node(model=MODEL)["node_id"] == "our_machine"


def test_a_total_outage_raises_rather_than_returning_a_dead_node(monkeypatch):
    _stub_health(monkeypatch, set())
    with pytest.raises(RuntimeError, match="No Ollama node"):
        ollama_nodes.select_available_node(model=MODEL)


# ── circuit breaker: no flapping, real recovery ─────────────────────────────


def test_one_transient_failure_does_not_take_a_node_out_of_service(monkeypatch):
    monkeypatch.setenv("OLLAMA_NODE_FAILURE_THRESHOLD", "3")
    ollama_nodes.record_failure("jagadeesh", "timeout")
    assert ollama_nodes.in_cooldown("jagadeesh") is False
    assert ollama_nodes.breaker_state("jagadeesh")["consecutive_failures"] == 1


def test_repeated_failures_open_the_breaker(monkeypatch):
    monkeypatch.setenv("OLLAMA_NODE_FAILURE_THRESHOLD", "3")
    monkeypatch.setenv("OLLAMA_NODE_COOLDOWN_SECONDS", "120")
    for _ in range(3):
        ollama_nodes.record_failure("jagadeesh", "timeout")
    assert ollama_nodes.in_cooldown("jagadeesh") is True
    assert ollama_nodes.breaker_state("jagadeesh")["cooldown_remaining_s"] > 0


def test_a_cooling_node_is_skipped_even_when_it_is_the_primary(monkeypatch):
    monkeypatch.setenv("OLLAMA_NODE_FAILURE_THRESHOLD", "2")
    ollama_nodes.set_primary_node("jagadeesh", force=True)
    _stub_health(monkeypatch, {"jagadeesh", "our_machine"})
    for _ in range(2):
        ollama_nodes.record_failure("jagadeesh", "timeout")
    assert ollama_nodes.select_available_node(model=MODEL)["node_id"] == "our_machine"


def test_a_recovered_node_rejoins_once_it_succeeds(monkeypatch):
    monkeypatch.setenv("OLLAMA_NODE_FAILURE_THRESHOLD", "2")
    ollama_nodes.set_primary_node("jagadeesh", force=True)
    _stub_health(monkeypatch, {"jagadeesh", "our_machine"})
    for _ in range(2):
        ollama_nodes.record_failure("jagadeesh", "timeout")
    assert ollama_nodes.in_cooldown("jagadeesh") is True

    ollama_nodes.record_success("jagadeesh")

    assert ollama_nodes.in_cooldown("jagadeesh") is False
    assert ollama_nodes.breaker_state("jagadeesh")["consecutive_failures"] == 0
    assert ollama_nodes.select_available_node(model=MODEL)["node_id"] == "jagadeesh"


def test_when_everything_is_cooling_the_pool_still_probes(monkeypatch):
    """A blanket outage must not become permanent because every breaker is open."""
    monkeypatch.setenv("OLLAMA_NODE_FAILURE_THRESHOLD", "1")
    _stub_health(monkeypatch, {"our_machine"})
    for node_id in ("rtx4060", "jagadeesh", "our_machine"):
        ollama_nodes.record_failure(node_id, "timeout")
    assert ollama_nodes.select_available_node(model=MODEL)["node_id"] == "our_machine"


def test_failover_never_rewrites_the_configured_primary(monkeypatch):
    """The anti-flap rule. Routing around a sick node is per-request; changing
    production's primary stays a deliberate admin action."""
    ollama_nodes.set_primary_node("rtx4060", force=True)
    _stub_health(monkeypatch, {"our_machine"})

    for _ in range(5):
        assert ollama_nodes.select_available_node(model=MODEL)["node_id"] == "our_machine"

    assert ollama_nodes.primary_node_id() == "rtx4060"


# ── inference verification ──────────────────────────────────────────────────


def test_verify_inference_requires_a_real_completion(monkeypatch):
    calls = []

    def fake_request(node_id, path, *, method="GET", payload=None, timeout=5):
        calls.append((node_id, path, payload))
        return {"response": "ok", "eval_count": 4, "eval_duration": 1_000_000_000}

    monkeypatch.setattr(ollama_nodes, "_request", fake_request)
    result = ollama_nodes.verify_inference("jagadeesh", model=MODEL)

    assert result["ok"] is True
    assert result["tokens_per_second"] == 4.0
    assert calls[0][1] == "/api/generate"
    assert ollama_nodes.breaker_state("jagadeesh")["consecutive_failures"] == 0


def test_an_empty_completion_counts_as_a_failure(monkeypatch):
    monkeypatch.setattr(
        ollama_nodes, "_request", lambda *a, **k: {"response": "   "}
    )
    result = ollama_nodes.verify_inference("jagadeesh", model=MODEL)
    assert result["ok"] is False
    assert ollama_nodes.breaker_state("jagadeesh")["consecutive_failures"] == 1


def test_a_generation_error_counts_as_a_failure(monkeypatch):
    def boom(*a, **k):
        raise OSError("connection reset")

    monkeypatch.setattr(ollama_nodes, "_request", boom)
    assert ollama_nodes.verify_inference("jagadeesh", model=MODEL)["ok"] is False
    assert ollama_nodes.breaker_state("jagadeesh")["last_error"] == "OSError"


# ── promotion must verify every required model, not just one ────────────────


def _stub_installed(monkeypatch, per_node):
    """node_health reporting a specific installed-model list per node."""

    def fake(node_id, *, model, timeout=5, deep=True):
        installed = per_node.get(node_id)
        reachable = installed is not None
        return {
            "id": node_id, "label": node_id, "primary": False,
            "status": "online" if reachable else "offline",
            "endpoint_reachable": reachable,
            "model": model,
            "model_available": bool(installed and model in installed),
            "model_loaded": False, "response_time_ms": 5, "error": None,
            "installed_models": installed or [],
            "breaker": ollama_nodes.breaker_state(node_id),
            "available": reachable,
        }

    monkeypatch.setattr(ollama_nodes, "node_health", fake)
    monkeypatch.setattr(
        ollama_nodes, "required_models", lambda: ["qwen2.5:7b", MODEL]
    )


def test_a_node_missing_the_text_model_cannot_become_primary(monkeypatch):
    """The regression this guard exists for. rtx4060 was promoted on the
    strength of the vision model alone, while lacking the text model that
    invite extraction actually calls, and booking broke until it was reverted.
    Fast on vision is not the same as able to serve."""
    _stub_installed(monkeypatch, {
        "rtx4060": [MODEL],                    # vision only
        "jagadeesh": ["qwen2.5:7b", MODEL],
        "our_machine": ["qwen2.5:7b", MODEL],
    })
    ollama_nodes.set_primary_node("jagadeesh", force=True)

    with pytest.raises(ValueError, match="missing required model"):
        ollama_nodes.set_primary_node("rtx4060")

    assert ollama_nodes.primary_node_id() == "jagadeesh", "primary must not move"


def test_the_error_names_the_model_that_is_missing(monkeypatch):
    _stub_installed(monkeypatch, {"rtx4060": [MODEL], "jagadeesh": ["qwen2.5:7b", MODEL]})
    with pytest.raises(ValueError, match="qwen2.5:7b"):
        ollama_nodes.set_primary_node("rtx4060")


def test_a_fully_stocked_node_promotes_normally(monkeypatch):
    _stub_installed(monkeypatch, {
        "rtx4060": ["qwen2.5:7b", MODEL],
        "jagadeesh": ["qwen2.5:7b", MODEL],
    })
    assert ollama_nodes.set_primary_node("rtx4060") == "rtx4060"
    assert ollama_nodes.primary_node_id() == "rtx4060"


def test_an_unreachable_node_cannot_become_primary(monkeypatch):
    _stub_installed(monkeypatch, {"jagadeesh": ["qwen2.5:7b", MODEL]})
    with pytest.raises(RuntimeError, match="not reachable"):
        ollama_nodes.set_primary_node("rtx4060")


def test_force_still_allows_a_deliberate_override(monkeypatch):
    """An admin who confirms the warning can still select a degraded node."""
    _stub_installed(monkeypatch, {"rtx4060": [MODEL], "jagadeesh": ["qwen2.5:7b", MODEL]})
    assert ollama_nodes.set_primary_node("rtx4060", force=True) == "rtx4060"


def test_missing_models_reports_every_gap(monkeypatch):
    _stub_installed(monkeypatch, {"rtx4060": []})
    assert ollama_nodes.missing_models("rtx4060") == ["qwen2.5:7b", MODEL]
