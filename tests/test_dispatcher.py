import json
from unittest.mock import MagicMock, patch

import pytest

from llmgate.dispatcher import call, FALLBACK_RATES
from llmgate.models import ProjectConfig


def _config() -> ProjectConfig:
    return ProjectConfig(project_id="test", db_path=":memory:", model_tiers={}, task_tiers={})


def _mock_response(status=200, body=None, headers=None):
    resp = MagicMock()
    resp.status_code = status
    resp.ok = status < 400
    resp.headers = headers or {}
    default_body = {
        "model": "qwen/qwen3-8b",
        "choices": [{"message": {"content": "Hello world"}}],
        "usage": {"prompt_tokens": 10, "completion_tokens": 5},
    }
    resp.json.return_value = body or default_body
    return resp


def test_successful_call():
    with patch("llmgate.dispatcher.requests.post", return_value=_mock_response()) as mock_post:
        with patch("llmgate.dispatcher.get_api_key", return_value="test-key"):
            result = call("Hello", None, "qwen/qwen3-8b", "test", _config())

    assert result["success"] is True
    assert result["content"] == "Hello world"
    assert result["input_tokens"] == 10
    assert result["output_tokens"] == 5
    assert result["escalated"] is False


def test_cost_from_header():
    headers = {"x-openrouter-response-cost": "0.00042"}
    with patch("llmgate.dispatcher.requests.post", return_value=_mock_response(headers=headers)):
        with patch("llmgate.dispatcher.get_api_key", return_value="test-key"):
            result = call("Hello", None, "qwen/qwen3-8b", "test", _config())

    assert abs(result["cost_usd"] - 0.00042) < 1e-10


def test_retry_on_429():
    responses = [_mock_response(status=429), _mock_response(status=429), _mock_response()]
    with patch("llmgate.dispatcher.requests.post", side_effect=responses):
        with patch("llmgate.dispatcher.get_api_key", return_value="test-key"):
            with patch("llmgate.dispatcher.time.sleep"):
                result = call("Hello", None, "qwen/qwen3-8b", "test", _config(), max_retries=2)

    assert result["success"] is True


def test_escalation_on_exhausted_retries():
    always_429 = _mock_response(status=429)
    success = _mock_response()
    # 2 retries fail, then escalation attempt succeeds
    responses = [always_429, always_429, always_429, success]
    with patch("llmgate.dispatcher.requests.post", side_effect=responses):
        with patch("llmgate.dispatcher.get_api_key", return_value="test-key"):
            with patch("llmgate.dispatcher.time.sleep"):
                result = call("Hello", None, "qwen/qwen3-8b", "test", _config(), max_retries=2)

    assert result["escalated"] is True
    assert result["success"] is True


def test_system_prompt_included():
    captured = {}

    def fake_post(url, headers, json, timeout):
        captured["messages"] = json["messages"]
        return _mock_response()

    with patch("llmgate.dispatcher.requests.post", side_effect=fake_post):
        with patch("llmgate.dispatcher.get_api_key", return_value="test-key"):
            call("Hello", "You are helpful.", "qwen/qwen3-8b", "test", _config())

    assert captured["messages"][0]["role"] == "system"
    assert captured["messages"][0]["content"] == "You are helpful."


def test_fallback_cost_computed_without_header():
    with patch("llmgate.dispatcher.requests.post", return_value=_mock_response()):
        with patch("llmgate.dispatcher.get_api_key", return_value="test-key"):
            result = call("Hello", None, "qwen/qwen3-8b", "test", _config())

    # 10 input + 5 output at small rates
    expected = (10 * 0.06 + 5 * 0.06) / 1_000_000
    assert abs(result["cost_usd"] - expected) < 1e-12


def test_http_error_returns_failure():
    with patch("llmgate.dispatcher.requests.post", return_value=_mock_response(status=400)):
        with patch("llmgate.dispatcher.get_api_key", return_value="test-key"):
            result = call("Hello", None, "qwen/qwen3-8b", "test", _config())

    assert result["success"] is False
    assert "400" in result["error_code"]
