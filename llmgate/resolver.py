from typing import Optional

from .config import DEFAULT_TIER_MAP, DEFAULT_TASK_TIERS
from .models import ProjectConfig, RoutingDecision


def resolve(
    task_type: str,
    complexity: str,
    config: ProjectConfig,
    force_tier: Optional[str] = None,
) -> RoutingDecision:
    task_tiers = {**DEFAULT_TASK_TIERS, **config.task_tiers}
    model_tiers = {**DEFAULT_TIER_MAP, **config.model_tiers}

    override = force_tier or config.tier_override
    if override:
        model = model_tiers.get(override, model_tiers["medium"])
        return RoutingDecision(
            task_type=task_type,
            complexity=complexity,
            tier=override,
            model=model,
            reasoning=f"force_tier={override!r} applied",
        )

    base_tier = task_tiers.get(task_type, "medium")
    tier = base_tier
    reasoning_parts = [f"task={task_type}, complexity={complexity}"]

    if complexity == "high" and task_type in ("reason", "synthesize"):
        tier = "large"
        reasoning_parts.append("reason/synthesize + high complexity -> large tier")
    elif complexity == "high" and base_tier == "small":
        tier = "medium"
        reasoning_parts.append(f"high complexity upgraded {base_tier!r} -> medium")
    else:
        reasoning_parts.append(f"base tier from task map: {base_tier!r}")

    model = model_tiers.get(tier, model_tiers["medium"])
    return RoutingDecision(
        task_type=task_type,
        complexity=complexity,
        tier=tier,
        model=model,
        reasoning=", ".join(reasoning_parts),
    )
