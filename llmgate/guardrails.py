import hashlib
import sys

from .models import ProjectConfig

_TIER_DOWNGRADE = {
    "large": "medium",
    "medium": "small",
    "small": "small",
}


def check_budget(config: ProjectConfig, db_path: str, requested_tier: str) -> str:
    from .ledger import get_spend_this_month

    spend = get_spend_this_month(db_path, config.project_id)
    if spend < config.monthly_budget_usd:
        return requested_tier

    downgraded = _TIER_DOWNGRADE.get(requested_tier, "small")
    print(
        f"[llmgate] WARNING: project '{config.project_id}' has spent "
        f"${spend:.4f} of ${config.monthly_budget_usd:.2f} monthly budget. "
        f"Downgrading tier {requested_tier!r} -> {downgraded!r}.",
        file=sys.stderr,
    )
    return downgraded


def prompt_fingerprint(prompt: str) -> str:
    sample = prompt[:200].encode("utf-8", errors="replace")
    return hashlib.sha256(sample).hexdigest()
