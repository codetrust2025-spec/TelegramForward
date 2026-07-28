import json

import pytest

from core import ai_gateway


def test_health_reports_model_availability(monkeypatch):
    monkeypatch.setattr(
        ai_gateway,
        "_request_json",
        lambda *args, **kwargs: {"models": [{"name": "qwen3.6:latest"}]},
    )
    result = ai_gateway.health(model="qwen3.6")
    assert result["endpoint_reachable"] is True
    assert result["model_available"] is True
    assert result["status"] == "healthy"
    assert result["diagnostic_status"] == "AVAILABLE"
    assert result["serviceReachable"] is True
    assert result["primaryModel"] == "qwen3.6"


def test_health_classifies_reverse_tunnel_failure(monkeypatch):
    monkeypatch.setenv("OLLAMA_EXPECT_REVERSE_SSH_TUNNEL", "true")
    monkeypatch.setattr(
        ai_gateway,
        "_request_json",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            ai_gateway.AIGatewayError(
                "Ollama is running on the laptop, but the VPS reverse SSH tunnel is unavailable.",
                code="REVERSE_SSH_TUNNEL_UNAVAILABLE",
            )
        ),
    )
    result = ai_gateway.health(model="qwen3.6")
    assert result["endpoint_reachable"] is False
    assert result["error_code"] == "REVERSE_SSH_TUNNEL_UNAVAILABLE"
    assert result["diagnostic_status"] == "TUNNEL_UNREACHABLE"


def test_health_separates_missing_primary_from_reachable_service(monkeypatch):
    monkeypatch.setattr(
        ai_gateway,
        "_request_json",
        lambda *args, **kwargs: {"models": [{"name": "qwen2.5:7b"}]},
    )
    result = ai_gateway.health(model="gemma4:12b")
    assert result["serviceReachable"] is True
    assert result["primaryModelAvailable"] is False
    assert result["diagnostic_status"] == "PRIMARY_MODEL_MISSING"


def test_invalid_base_url_is_configuration_error(monkeypatch):
    monkeypatch.setenv("OLLAMA_BASE_URL", "not-a-url")
    result = ai_gateway.health(model="gemma4:12b")
    assert result["diagnostic_status"] == "CONFIGURATION_ERROR"
    assert result["serviceReachable"] is False


def test_missing_model_stops_before_chat(monkeypatch):
    monkeypatch.setattr(
        ai_gateway,
        "health",
        lambda **kwargs: {
            "endpoint_reachable": True,
            "model_available": False,
            "error_message": "missing",
            "error_code": "OLLAMA_MODEL_NOT_FOUND",
        },
    )
    with pytest.raises(ai_gateway.AIGatewayError) as error:
        ai_gateway.chat_structured(messages=[], schema={}, model="missing")
    assert error.value.code == "OLLAMA_MODEL_NOT_FOUND"


def test_timeout_retries_three_times_then_falls_back(monkeypatch):
    calls = []
    monkeypatch.setenv("OLLAMA_MAX_RETRIES", "3")
    monkeypatch.setattr(ai_gateway, "health", lambda **kwargs: {
        "endpoint_reachable": True, "model_available": True,
        "error_message": None, "error_code": None,
    })
    monkeypatch.setattr(ai_gateway.time, "sleep", lambda seconds: None)

    def fail(*args, **kwargs):
        calls.append(kwargs)
        raise ai_gateway.AIGatewayError("timed out", code="OLLAMA_REQUEST_TIMEOUT")

    monkeypatch.setattr(ai_gateway, "_request_json", fail)
    with pytest.raises(ai_gateway.AIGatewayError) as error:
        ai_gateway.chat_structured(messages=[{"role": "user", "content": "x"}], schema={}, model="qwen3.6")
    assert error.value.code == "OLLAMA_REQUEST_TIMEOUT"
    assert len(calls) == 4


def test_invalid_json_is_not_retried(monkeypatch):
    calls = []
    monkeypatch.setattr(ai_gateway, "health", lambda **kwargs: {
        "endpoint_reachable": True, "model_available": True,
        "error_message": None, "error_code": None,
    })

    def fail(*args, **kwargs):
        calls.append(1)
        raise ai_gateway.AIGatewayError("invalid", code="OLLAMA_INVALID_JSON")

    monkeypatch.setattr(ai_gateway, "_request_json", fail)
    with pytest.raises(ai_gateway.AIGatewayError) as error:
        ai_gateway.chat_structured(messages=[{"role": "user", "content": "x"}], schema={}, model="qwen3.6")
    assert error.value.code == "OLLAMA_INVALID_JSON"
    assert len(calls) == 1


@pytest.mark.parametrize(
    ("status", "body", "code"),
    [
        (500, '{"error":"failed to load model runner"}', "OLLAMA_MODEL_LOAD_FAILED"),
        (400, '{"error":"invalid format"}', "OLLAMA_BAD_REQUEST"),
        (404, '{"error":"model not found"}', "OLLAMA_MODEL_NOT_FOUND"),
        (500, '{"error":"unexpected"}', "OLLAMA_INTERNAL_ERROR"),
    ],
)
def test_http_error_classification(status, body, code):
    assert ai_gateway._http_error_code(status, body) == code


def test_tag_refresh_does_not_hide_a_newer_inference_failure():
    from core import ollama_status

    ollama_status.record_request_success(10)
    ollama_status.record_request_failure("OLLAMA_MODEL_LOAD_FAILED", "load failed")
    refreshed = ollama_status.record_health(
        status="healthy", endpoint_reachable=True, model_available=True,
        error_code=None, error_message=None,
    )
    assert refreshed["status"] == "degraded"
    assert refreshed["error_code"] == "OLLAMA_MODEL_LOAD_FAILED"

    ollama_status.record_request_success(10)
    assert ollama_status.snapshot()["status"] == "healthy"


def test_structured_chat_validates_and_normalizes_json(monkeypatch):
    monkeypatch.setattr(ai_gateway, "health", lambda **kwargs: {
        "endpoint_reachable": True, "model_available": True,
        "error_message": None, "error_code": None,
    })
    monkeypatch.setattr(
        ai_gateway,
        "_request_json",
        lambda *args, **kwargs: {"message": {"content": '{"ok": true}'}},
    )
    result = ai_gateway.chat_structured(
        messages=[{"role": "user", "content": "test"}],
        schema={
            "type": "object",
            "properties": {"ok": {"type": "boolean"}},
            "required": ["ok"],
            "additionalProperties": False,
        },
        model="qwen2.5:7b",
        workload="test",
    )
    assert json.loads(result.content) == {"ok": True}


def test_chat_sends_explicit_think_setting(monkeypatch):
    captured = {}
    monkeypatch.setattr(ai_gateway, "health", lambda **kwargs: {
        "endpoint_reachable": True, "model_available": True,
        "error_message": None, "error_code": None,
    })

    def respond(*args, **kwargs):
        captured.update(json.loads(kwargs["body"]))
        return {"message": {"content": '{"ok": true}'}}

    monkeypatch.setattr(ai_gateway, "_request_json", respond)
    ai_gateway.chat(
        messages=[{"role": "user", "content": "test"}],
        model="qwen3-vl:8b",
        think=False,
    )

    assert captured["think"] is False


def test_structured_chat_rejects_schema_mismatch(monkeypatch):
    monkeypatch.setattr(ai_gateway, "health", lambda **kwargs: {
        "endpoint_reachable": True, "model_available": True,
        "error_message": None, "error_code": None,
    })
    monkeypatch.setattr(
        ai_gateway,
        "_request_json",
        lambda *args, **kwargs: {"message": {"content": '{"ok": "yes"}'}},
    )
    with pytest.raises(ai_gateway.AIGatewayError) as error:
        ai_gateway.chat_structured(
            messages=[{"role": "user", "content": "test"}],
            schema={
                "type": "object",
                "properties": {"ok": {"type": "boolean"}},
                "required": ["ok"],
            },
            model="qwen2.5:7b",
            workload="test",
        )
    assert error.value.code == "OLLAMA_SCHEMA_VALIDATION_FAILED"
