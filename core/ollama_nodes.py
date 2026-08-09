"""Configuration, routing and administration for the Ollama inference pool."""

from __future__ import annotations

import http.client
import json
import os
import socket
import tempfile
import threading
import time
import urllib.parse
from pathlib import Path
from typing import Any

_LOCK = threading.RLock()
_DEFAULT_PRIMARY = "jagadeesh"


def _env_flag(name: str, default: bool = False) -> bool:
    raw = (os.getenv(name) or "").strip().lower()
    if not raw:
        return default
    return raw in {"1", "true", "yes", "on", "enabled"}


def configured_nodes() -> list[dict[str, str]]:
    """The inference pool, in failover order.

    Order is preference, not health: selection walks this list and skips nodes
    that fail their model check. Ids are persisted in runtime state and quoted
    in the admin API, so they never change — ``our_machine`` stays
    ``our_machine`` even though the machine is Praveen's laptop. Business logic
    keys on the id; the label is only ever displayed.
    """
    nodes = [
        {
            "id": "rtx4060",
            "label": "RTX 4060",
            "base_url": (
                os.getenv("OLLAMA_NODE_RTX4060_URL")
                or "http://127.0.0.1:11437"
            ).rstrip("/"),
        },
        {
            "id": "jagadeesh",
            "label": "Jagadeesh",
            "base_url": (
                os.getenv("OLLAMA_NODE_JAGADEESH_URL")
                or os.getenv("OLLAMA_BASE_URL")
                or "http://127.0.0.1:11435"
            ).rstrip("/"),
        },
        {
            "id": "our_machine",
            "label": "Praveen",
            "base_url": (
                os.getenv("OLLAMA_NODE_OUR_MACHINE_URL")
                or "http://127.0.0.1:11436"
            ).rstrip("/"),
        },
    ]
    # The VPS runs its own Ollama, but on the same four CPU cores that serve the
    # web application and with no GPU. Measured CPU-only inference on an
    # identical job took 171s against 4.7s on a GPU node, so this is an
    # emergency fallback that has to be turned on deliberately, never a default.
    if _env_flag("OLLAMA_ENABLE_VPS_LOCAL"):
        nodes.append(
            {
                "id": "vps_local",
                "label": "VPS Local",
                "base_url": (
                    os.getenv("OLLAMA_NODE_VPS_LOCAL_URL")
                    or "http://127.0.0.1:11434"
                ).rstrip("/"),
            }
        )
    return nodes


def _state_path() -> Path:
    configured = (os.getenv("OLLAMA_NODE_STATE_FILE") or "").strip()
    if configured:
        return Path(configured)
    return Path(__file__).resolve().parents[1] / "data" / "ollama_nodes_state.json"


def _valid_node_ids() -> set[str]:
    return {node["id"] for node in configured_nodes()}


def primary_node_id() -> str:
    default = (os.getenv("OLLAMA_PRIMARY_NODE") or _DEFAULT_PRIMARY).strip()
    if default not in _valid_node_ids():
        default = _DEFAULT_PRIMARY
    with _LOCK:
        try:
            saved = json.loads(_state_path().read_text(encoding="utf-8"))
            selected = str(saved.get("primary_node") or "")
            return selected if selected in _valid_node_ids() else default
        except (FileNotFoundError, OSError, ValueError, TypeError):
            return default


def set_primary_node(node_id: str) -> str:
    selected = str(node_id or "").strip()
    if selected not in _valid_node_ids():
        raise ValueError("Unknown Ollama node")
    path = _state_path()
    with _LOCK:
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = json.dumps({"primary_node": selected}, indent=2) + "\n"
        temporary: Path | None = None
        try:
            with tempfile.NamedTemporaryFile(
                "w",
                encoding="utf-8",
                dir=path.parent,
                prefix=f".{path.name}.",
                suffix=".tmp",
                delete=False,
            ) as handle:
                handle.write(payload)
                handle.flush()
                os.fsync(handle.fileno())
                temporary = Path(handle.name)
            os.replace(temporary, path)
        finally:
            if temporary and temporary.exists():
                temporary.unlink(missing_ok=True)
    return selected


def node(node_id: str) -> dict[str, str]:
    selected = str(node_id or "").strip()
    for item in configured_nodes():
        if item["id"] == selected:
            return item
    raise ValueError("Unknown Ollama node")


def base_url_for(node_id: str) -> str:
    return node(node_id)["base_url"]


def primary_base_url() -> str:
    return base_url_for(primary_node_id())


def inference_host_id(node_id: str | None = None) -> str:
    return f"{node_id or primary_node_id()}-ollama"


def _model_available(configured: str, installed: list[str]) -> bool:
    wanted = configured.removesuffix(":latest")
    return any(name.removesuffix(":latest") == wanted for name in installed)


def _request(
    node_id: str,
    path: str,
    *,
    method: str = "GET",
    payload: dict[str, Any] | None = None,
    timeout: float = 5,
) -> dict[str, Any]:
    parsed = urllib.parse.urlsplit(base_url_for(node_id))
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise ValueError("Invalid Ollama node URL")
    connection_type = (
        http.client.HTTPSConnection
        if parsed.scheme == "https"
        else http.client.HTTPConnection
    )
    connection = connection_type(parsed.hostname, parsed.port, timeout=timeout)
    try:
        body = json.dumps(payload).encode("utf-8") if payload is not None else None
        target = f"{parsed.path.rstrip('/')}{path}" or path
        connection.request(
            method,
            target,
            body=body,
            headers={"Content-Type": "application/json"},
        )
        response = connection.getresponse()
        raw = response.read().decode("utf-8")
        if response.status >= 400:
            raise RuntimeError(f"Ollama returned HTTP {response.status}")
        return json.loads(raw) if raw else {}
    finally:
        connection.close()


def node_health(
    node_id: str, *, model: str, timeout: float = 5, deep: bool = True
) -> dict[str, Any]:
    """Probe a node. ``deep`` adds GPU and version detail for the admin screen.

    Routing calls this on every request, so the selection path passes
    deep=False and pays for one HTTP round trip rather than three.
    """
    item = node(node_id)
    started = time.monotonic()
    result: dict[str, Any] = {
        "id": item["id"],
        "label": item["label"],
        "primary": item["id"] == primary_node_id(),
        "status": "offline",
        "endpoint_reachable": False,
        "model": model,
        "model_available": False,
        "model_loaded": False,
        "response_time_ms": None,
        "error": None,
    }
    try:
        tags = _request(node_id, "/api/tags", timeout=timeout)
        installed = [
            str(entry.get("name") or entry.get("model") or "")
            for entry in tags.get("models", [])
        ]
        loaded: list[str] = []
        processes: dict[str, Any] = {}
        try:
            processes = (
                _request(node_id, "/api/ps", timeout=timeout) if deep else {}
            )
            loaded = [
                str(entry.get("name") or entry.get("model") or "")
                for entry in processes.get("models", [])
            ]
        except (OSError, RuntimeError, ValueError, json.JSONDecodeError):
            # Older Ollama builds can be healthy without exposing /api/ps.
            loaded = []
        result.update(
            {
                "status": "online" if _model_available(model, installed) else "degraded",
                "endpoint_reachable": True,
                "model_available": _model_available(model, installed),
                "model_loaded": _model_available(model, loaded),
                "response_time_ms": int((time.monotonic() - started) * 1000),
                "installed_models": installed,
                "loaded_models": loaded,
            }
        )
        # How much of the loaded model sits in VRAM is the only reliable signal
        # from the Ollama API that a node is really using its GPU. A node
        # reporting 0 here is running on CPU however good its spec sheet is.
        try:
            for entry in (processes or {}).get("models", []):
                total = int(entry.get("size") or 0)
                vram = int(entry.get("size_vram") or 0)
                if not total:
                    continue
                result["gpu"] = {
                    "size_bytes": total,
                    "size_vram_bytes": vram,
                    "gpu_fraction": round(vram / total, 3),
                    "accelerated": vram > 0,
                }
                break
        except (AttributeError, TypeError, ValueError):
            pass
        if deep:
            try:
                result["ollama_version"] = str(
                    _request(node_id, "/api/version", timeout=timeout).get("version")
                    or ""
                )
            except (OSError, RuntimeError, ValueError, json.JSONDecodeError):
                result["ollama_version"] = ""
    except (OSError, RuntimeError, ValueError, json.JSONDecodeError, socket.timeout) as exc:
        result.update(
            {
                "response_time_ms": int((time.monotonic() - started) * 1000),
                "error": type(exc).__name__,
            }
        )
    result["breaker"] = breaker_state(node_id)
    # Reachable plus the model present is the most this cheap probe can claim.
    # Only verify_inference() proves the node can actually generate.
    result["available"] = bool(
        result["endpoint_reachable"]
        and result["model_available"]
        and not result["breaker"]["in_cooldown"]
    )
    return result


# ── circuit breaker ─────────────────────────────────────────────────────────
#
# Kept in memory rather than in the state file. Persisting it would rewrite the
# file on every failed probe, and a breaker that survives a restart would keep a
# node out of service for reasons nobody can see. A fresh process starts by
# probing everything, which is the safe direction.
_BREAKERS: dict[str, dict[str, Any]] = {}


def _failure_threshold() -> int:
    try:
        return max(1, int(os.getenv("OLLAMA_NODE_FAILURE_THRESHOLD") or 3))
    except ValueError:
        return 3


def _cooldown_seconds() -> float:
    try:
        return max(0.0, float(os.getenv("OLLAMA_NODE_COOLDOWN_SECONDS") or 120))
    except ValueError:
        return 120.0


def _breaker(node_id: str) -> dict[str, Any]:
    with _LOCK:
        return dict(
            _BREAKERS.setdefault(
                node_id,
                {
                    "consecutive_failures": 0,
                    "last_success_at": None,
                    "last_failure_at": None,
                    "last_error": None,
                    "cooling_until": 0.0,
                },
            )
        )


def record_success(node_id: str) -> None:
    with _LOCK:
        state = _BREAKERS.setdefault(node_id, {})
        state.update(
            {
                "consecutive_failures": 0,
                "last_success_at": time.time(),
                "last_error": None,
                "cooling_until": 0.0,
            }
        )


def record_failure(node_id: str, error: str = "") -> None:
    """One timeout is not a dead node; a run of them is."""
    with _LOCK:
        state = _BREAKERS.setdefault(node_id, {"consecutive_failures": 0})
        failures = int(state.get("consecutive_failures") or 0) + 1
        state["consecutive_failures"] = failures
        state["last_failure_at"] = time.time()
        state["last_error"] = error or state.get("last_error")
        if failures >= _failure_threshold():
            state["cooling_until"] = time.monotonic() + _cooldown_seconds()


def in_cooldown(node_id: str) -> bool:
    return float(_breaker(node_id).get("cooling_until") or 0.0) > time.monotonic()


def reset_breakers() -> None:
    with _LOCK:
        _BREAKERS.clear()


def breaker_state(node_id: str) -> dict[str, Any]:
    state = _breaker(node_id)
    cooling = float(state.get("cooling_until") or 0.0)
    return {
        "consecutive_failures": int(state.get("consecutive_failures") or 0),
        "last_success_at": state.get("last_success_at"),
        "last_failure_at": state.get("last_failure_at"),
        "last_error": state.get("last_error"),
        "in_cooldown": cooling > time.monotonic(),
        "cooldown_remaining_s": max(0, int(cooling - time.monotonic())) if cooling else 0,
    }


def verify_inference(
    node_id: str, *, model: str, timeout: float = 60
) -> dict[str, Any]:
    """Prove the node can actually run the model.

    An open port says nothing: a node can accept TCP, list the model in
    /api/tags and still fail every generation. Health that matters is a
    completed response.
    """
    started = time.monotonic()
    try:
        payload = _request(
            node_id,
            "/api/generate",
            method="POST",
            payload={
                "model": model,
                "prompt": "Reply with the single word: ok",
                "stream": False,
                "options": {"temperature": 0, "num_predict": 4},
            },
            timeout=timeout,
        )
        text = str(payload.get("response") or "").strip()
        elapsed_ms = int((time.monotonic() - started) * 1000)
        if not text:
            record_failure(node_id, "empty response")
            return {"ok": False, "latency_ms": elapsed_ms, "error": "empty response"}
        eval_count = int(payload.get("eval_count") or 0)
        eval_ns = int(payload.get("eval_duration") or 0)
        record_success(node_id)
        return {
            "ok": True,
            "latency_ms": elapsed_ms,
            "tokens_per_second": (
                round(eval_count / (eval_ns / 1e9), 2) if eval_ns else None
            ),
            "load_duration_s": round(int(payload.get("load_duration") or 0) / 1e9, 2),
        }
    except (OSError, RuntimeError, ValueError, json.JSONDecodeError, socket.timeout) as exc:
        record_failure(node_id, type(exc).__name__)
        return {
            "ok": False,
            "latency_ms": int((time.monotonic() - started) * 1000),
            "error": type(exc).__name__,
        }


def candidate_order() -> list[str]:
    """Preference order for routing: the chosen primary, then the rest."""
    ordered = [item["id"] for item in configured_nodes()]
    primary = primary_node_id()
    return [primary] + [item for item in ordered if item != primary]


def select_available_node(
    *,
    model: str,
    timeout: float = 5,
    require_inference: bool = False,
) -> dict[str, Any]:
    """Pick where this request should run.

    Walks the preference order and returns the first node whose model check
    passes, skipping any that is cooling off. This never rewrites the persisted
    primary: routing around a sick node is a per-request decision, so a blip
    cannot move production's configured primary. Changing that stays an
    explicit admin action.
    """
    attempts: list[dict[str, Any]] = []
    order = candidate_order()
    cooling = [nid for nid in order if in_cooldown(nid)]
    # If every node is cooling there is nothing to be gained by refusing; try
    # them anyway so a total outage still gets probed rather than hard-failing.
    usable = [nid for nid in order if nid not in cooling] or order

    for node_id in usable:
        status = node_health(node_id, model=model, timeout=timeout, deep=False)
        if not status["endpoint_reachable"]:
            record_failure(node_id, status.get("error") or "unreachable")
            attempts.append({"node": node_id, "reason": "unreachable"})
            continue
        if not status["model_available"]:
            record_failure(node_id, "model missing")
            attempts.append({"node": node_id, "reason": "model missing"})
            continue
        if require_inference:
            proof = verify_inference(node_id, model=model, timeout=max(timeout, 30))
            if not proof["ok"]:
                attempts.append({"node": node_id, "reason": proof.get("error")})
                continue
        else:
            record_success(node_id)
        return {
            "node_id": node_id,
            "base_url": base_url_for(node_id),
            "was_primary": node_id == primary_node_id(),
            "attempts": attempts,
        }

    raise RuntimeError(
        "No Ollama node could serve this request: "
        + "; ".join(f"{a['node']} ({a['reason']})" for a in attempts)
    )


def unload_model(node_id: str, *, model: str, timeout: float = 30) -> dict[str, Any]:
    before = node_health(node_id, model=model, timeout=min(timeout, 5))
    if not before["endpoint_reachable"]:
        raise RuntimeError("The selected Ollama node is offline")
    if not before["model_available"]:
        raise RuntimeError("The configured model is not installed on this node")
    _request(
        node_id,
        "/api/generate",
        method="POST",
        payload={"model": model, "keep_alive": 0},
        timeout=timeout,
    )
    deadline = time.monotonic() + min(timeout, 3)
    after = node_health(node_id, model=model, timeout=min(timeout, 5))
    while after["model_loaded"] and time.monotonic() < deadline:
        time.sleep(0.25)
        after = node_health(node_id, model=model, timeout=min(timeout, 5))
    return {"node": after, "unloaded": not after["model_loaded"]}
