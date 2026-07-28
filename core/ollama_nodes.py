"""Configuration and safe administration for the two Ollama inference nodes."""

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


def configured_nodes() -> list[dict[str, str]]:
    return [
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
            "label": "Our machine",
            "base_url": (
                os.getenv("OLLAMA_NODE_OUR_MACHINE_URL")
                or "http://127.0.0.1:11436"
            ).rstrip("/"),
        },
    ]


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


def node_health(node_id: str, *, model: str, timeout: float = 5) -> dict[str, Any]:
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
        try:
            processes = _request(node_id, "/api/ps", timeout=timeout)
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
    except (OSError, RuntimeError, ValueError, json.JSONDecodeError, socket.timeout) as exc:
        result.update(
            {
                "response_time_ms": int((time.monotonic() - started) * 1000),
                "error": type(exc).__name__,
            }
        )
    return result


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
