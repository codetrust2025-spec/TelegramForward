"""Central model routing policy for TeleAutomation AI workloads.

Feature modules must ask the AI gateway for a route instead of hard-coding
Ollama model names. Environment variables remain the deployment override.
"""

from __future__ import annotations

import os


MODEL_ROUTES = {
    # Keep the defaults usable on the 16 GB laptop that hosts Ollama.  The
    # qwen3.6 image needs more than 22 GB of CPU buffers and can spend most of
    # the request timeout merely loading.  Larger deployments may still opt in
    # to it with OLLAMA_MAIL_MODEL.
    "recruitment_email_primary": ("OLLAMA_MAIL_MODEL", "qwen2.5:7b"),
    "recruitment_email_validator": ("AI_RECRUITMENT_VALIDATOR_MODEL", "gemma2:2b"),
    "recruitment_document_vision": ("OLLAMA_VISION_MODEL", "qwen2.5vl:7b"),
}


def model_for(route: str) -> str:
    """Return the configured model for a named AI workload."""
    try:
        variable, default = MODEL_ROUTES[route]
    except KeyError as exc:
        raise ValueError(f"Unknown AI model route: {route}") from exc
    legacy = os.getenv("AI_RECRUITMENT_MODEL") if route == "recruitment_email_primary" else None
    return (os.getenv(variable) or legacy or default).strip()


def configured_model_routes() -> dict[str, str]:
    return {route: model_for(route) for route in MODEL_ROUTES}
