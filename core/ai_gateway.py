"""Central, bounded gateway for local Ollama requests.

New AI features must use this module rather than calling Ollama from routes,
providers, or persistence code.  It deliberately exposes a small synchronous
API so callers can execute it through the application's background workers.
"""

from __future__ import annotations

import json
import logging
import os
import threading
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger("teleautomation.ai_gateway")
_slots = threading.BoundedSemaphore(max(1, int(os.getenv("AI_OLLAMA_MAX_CONCURRENCY", "1"))))


@dataclass(frozen=True)
class AIResult:
    content: str
    model: str
    duration_ms: int


class AIGatewayError(RuntimeError):
    pass


def configured_models() -> dict[str, str]:
    return {
        "text": (os.getenv("AI_RECRUITMENT_MODEL") or os.getenv("OLLAMA_REASONING_MODEL") or "qwen2.5:7b").strip(),
        "fallback": (os.getenv("AI_RECRUITMENT_FALLBACK_MODEL") or "").strip(),
        "vision": (os.getenv("OLLAMA_VISION_MODEL") or "qwen2.5vl:7b").strip(),
    }


def chat_structured(
    *,
    messages: list[dict[str, Any]],
    schema: dict[str, Any],
    model: str | None = None,
    timeout: float | None = None,
    temperature: float = 0,
    images: list[str] | None = None,
) -> AIResult:
    """Return a schema-constrained Ollama response with bounded concurrency."""
    chosen = (model or configured_models()["text"]).strip()
    if not chosen:
        raise AIGatewayError("No AI model is configured")
    base = (os.getenv("OLLAMA_BASE_URL") or "http://127.0.0.1:11434").rstrip("/")
    wait = float(os.getenv("AI_RECRUITMENT_QUEUE_WAIT_SECONDS", "30"))
    if not _slots.acquire(timeout=wait):
        raise AIGatewayError("AI queue is busy; request timed out")
    started = time.monotonic()
    try:
        prepared_messages = [dict(message) for message in messages]
        if images and prepared_messages:
            prepared_messages[-1]["images"] = images
        body = json.dumps({
            "model": chosen,
            "messages": prepared_messages,
            "stream": False,
            "format": schema,
            "options": {"temperature": temperature},
        }).encode("utf-8")
        req = urllib.request.Request(
            f"{base}/api/chat", data=body,
            headers={"Content-Type": "application/json"}, method="POST",
        )
        try:
            with urllib.request.urlopen(
                req, timeout=timeout or float(os.getenv("AI_RECRUITMENT_TIMEOUT_SECONDS", "120"))
            ) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except (urllib.error.URLError, TimeoutError, ValueError) as exc:
            logger.warning("AI request failed model=%s error=%s", chosen, type(exc).__name__)
            raise AIGatewayError("Local AI service is unavailable") from exc
        content = str((payload.get("message") or {}).get("content") or "").strip()
        if not content:
            raise AIGatewayError("AI returned an empty response")
        return AIResult(content=content, model=chosen, duration_ms=int((time.monotonic() - started) * 1000))
    finally:
        _slots.release()


def health() -> dict[str, Any]:
    base = (os.getenv("OLLAMA_BASE_URL") or "http://127.0.0.1:11434").rstrip("/")
    try:
        with urllib.request.urlopen(f"{base}/api/tags", timeout=3) as response:
            payload = json.loads(response.read().decode("utf-8"))
        return {"available": True, "models": [m.get("name") for m in payload.get("models", [])]}
    except Exception:
        return {"available": False, "models": []}
