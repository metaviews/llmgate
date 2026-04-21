import time
from typing import Optional

import requests

from .config import DEFAULT_TIER_MAP, get_api_key
from .models import ProjectConfig

FALLBACK_RATES = {
    "small":  {"input": 0.06,  "output": 0.06},
    "medium": {"input": 0.14,  "output": 0.14},
    "large":  {"input": 0.90,  "output": 0.90},
}

_OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"

_TIER_UPGRADE = {
    "small": "medium",
    "medium": "large",
    "large": "large",
}


def _tier_for_model(model: str, config: ProjectConfig) -> str:
    model_tiers = {**DEFAULT_TIER_MAP, **config.model_tiers}
    for tier, m in model_tiers.items():
        if m == model:
            return tier
    return "medium"


def _compute_cost(input_tokens: int, output_tokens: int, tier: str) -> float:
    rates = FALLBACK_RATES.get(tier, FALLBACK_RATES["medium"])
    return (input_tokens * rates["input"] + output_tokens * rates["output"]) / 1_000_000


def _build_messages(prompt: str, system_prompt: Optional[str]) -> list[dict]:
    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": prompt})
    return messages


def call(
    prompt: str,
    system_prompt: Optional[str],
    model: str,
    project_id: str,
    config: ProjectConfig,
    max_retries: int = 2,
    timeout_s: int = 60,
) -> dict:
    api_key = get_api_key()
    headers = {
        "Authorization": f"Bearer {api_key}",
        "HTTP-Referer": "llmgate",
        "X-Title": "llmgate",
        "Content-Type": "application/json",
    }

    current_model = model
    escalated = False

    for attempt in range(max_retries + 2):
        messages = _build_messages(prompt, system_prompt)
        body = {
            "model": current_model,
            "messages": messages,
            "max_tokens": 2048,
        }

        t_start = time.monotonic()
        try:
            resp = requests.post(
                _OPENROUTER_URL,
                headers=headers,
                json=body,
                timeout=timeout_s,
            )
        except requests.RequestException as exc:
            if attempt >= max_retries:
                return _error_result(current_model, str(exc), escalated)
            time.sleep(2 ** attempt)
            continue

        latency_ms = int((time.monotonic() - t_start) * 1000)

        if resp.status_code == 429 or resp.status_code >= 500:
            if attempt < max_retries:
                time.sleep(2 ** attempt)
                continue
            # Escalate to next tier after retries exhausted
            current_tier = _tier_for_model(current_model, config)
            next_tier = _TIER_UPGRADE.get(current_tier, current_tier)
            if next_tier != current_tier:
                model_tiers = {**DEFAULT_TIER_MAP, **config.model_tiers}
                current_model = model_tiers.get(next_tier, current_model)
                escalated = True
                continue
            return _error_result(current_model, f"HTTP {resp.status_code}", escalated)

        if not resp.ok:
            return _error_result(current_model, f"HTTP {resp.status_code}", escalated)

        data = resp.json()

        actual_model = data.get("model", current_model)
        usage = data.get("usage", {})
        input_tokens = usage.get("prompt_tokens", 0)
        output_tokens = usage.get("completion_tokens", 0)

        cost_header = resp.headers.get("x-openrouter-response-cost")
        if cost_header:
            try:
                cost_usd = float(cost_header)
            except ValueError:
                cost_usd = _compute_cost(input_tokens, output_tokens, _tier_for_model(current_model, config))
        else:
            cost_usd = _compute_cost(input_tokens, output_tokens, _tier_for_model(current_model, config))

        content = ""
        choices = data.get("choices", [])
        if choices:
            content = choices[0].get("message", {}).get("content", "")

        return {
            "content": content,
            "model": actual_model,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "cost_usd": cost_usd,
            "latency_ms": latency_ms,
            "success": True,
            "error_code": None,
            "escalated": escalated,
        }

    return _error_result(current_model, "max_retries exceeded", escalated)


def _error_result(model: str, error_code: str, escalated: bool) -> dict:
    return {
        "content": "",
        "model": model,
        "input_tokens": 0,
        "output_tokens": 0,
        "cost_usd": 0.0,
        "latency_ms": 0,
        "success": False,
        "error_code": error_code,
        "escalated": escalated,
    }
