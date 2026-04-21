from llmgate.models import ProjectConfig
from llmgate.resolver import resolve


def _config(**kwargs) -> ProjectConfig:
    defaults = dict(project_id="test", db_path=":memory:", model_tiers={}, task_tiers={})
    defaults.update(kwargs)
    return ProjectConfig(**defaults)


def test_summarize_low_small_tier():
    decision = resolve("summarize", "low", _config())
    assert decision.tier == "small"


def test_reason_high_large_tier():
    decision = resolve("reason", "high", _config())
    assert decision.tier == "large"


def test_small_high_complexity_upgrades_to_medium():
    # extract is mapped to small, high complexity should upgrade
    decision = resolve("extract", "high", _config())
    assert decision.tier == "medium"


def test_force_tier_overrides_everything():
    decision = resolve("reason", "high", _config(), force_tier="small")
    assert decision.tier == "small"


def test_synthesize_high_goes_to_large():
    decision = resolve("synthesize", "high", _config())
    assert decision.tier == "large"


def test_config_tier_override():
    config = _config(tier_override="medium")
    decision = resolve("reason", "high", config)
    assert decision.tier == "medium"


def test_reasoning_field_populated():
    decision = resolve("summarize", "low", _config())
    assert decision.reasoning


def test_model_returned():
    decision = resolve("summarize", "low", _config())
    assert decision.model  # non-empty string
