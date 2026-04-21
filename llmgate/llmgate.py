from datetime import datetime
from typing import Optional

from .classifier import classify
from .config import load_config, set_session_tier
from .dispatcher import call as dispatch_call
from .guardrails import check_budget, prompt_fingerprint
from .ledger import get_spend_this_month, init_db, log_call
from .models import CallRecord
from .resolver import resolve
from . import stats as _stats_module


def ask(
    prompt: str,
    project_id: str,
    task_hint: Optional[str] = None,
    force_tier: Optional[str] = None,
    start_dir: Optional[str] = None,
) -> dict:
    config = load_config(project_id, start_dir=start_dir)
    db_path = config.db_path
    init_db(db_path)

    task_type, complexity = classify(prompt, task_hint=task_hint)
    decision = resolve(task_type, complexity, config, force_tier=force_tier)

    final_tier = check_budget(config, db_path, decision.tier)
    if final_tier != decision.tier:
        from .config import DEFAULT_TIER_MAP
        model_tiers = {**DEFAULT_TIER_MAP, **config.model_tiers}
        decision.tier = final_tier
        decision.model = model_tiers.get(final_tier, model_tiers["medium"])
        decision.reasoning += f" [budget downgrade -> {final_tier}]"

    system_prompt = config.system_prompt
    fingerprint = prompt_fingerprint(prompt)

    result = dispatch_call(
        prompt=prompt,
        system_prompt=system_prompt,
        model=decision.model,
        project_id=project_id,
        config=config,
    )

    record = CallRecord(
        project_id=project_id,
        task_type=task_type,
        tier=decision.tier,
        model=result["model"],
        input_tokens=result["input_tokens"],
        output_tokens=result["output_tokens"],
        cost_usd=result["cost_usd"],
        latency_ms=result["latency_ms"],
        success=result["success"],
        escalated=result["escalated"],
        confidence=None,
        error_code=result["error_code"],
        timestamp=datetime.utcnow(),
        prompt_fingerprint=fingerprint,
    )
    log_call(db_path, record)

    return {
        "content": result["content"],
        "model": result["model"],
        "tier": decision.tier,
        "task_type": task_type,
        "input_tokens": result["input_tokens"],
        "output_tokens": result["output_tokens"],
        "cost_usd": result["cost_usd"],
        "latency_ms": result["latency_ms"],
        "success": result["success"],
        "escalated": result["escalated"],
        "routing_reasoning": decision.reasoning,
    }


def stats(project_id: str, period: str = "month", start_dir: Optional[str] = None) -> str:
    config = load_config(project_id, start_dir=start_dir)
    return _stats_module.summary(config.db_path, project_id, period=period)


def cost_today(project_id: str, start_dir: Optional[str] = None) -> float:
    config = load_config(project_id, start_dir=start_dir)
    rows = _stats_module._fetch(config.db_path, project_id, "day")
    return sum(r["cost_usd"] for r in rows)


def set_tier(project_id: str, tier: str) -> None:
    set_session_tier(project_id, tier)
