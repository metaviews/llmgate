import os
import sys
from pathlib import Path
from typing import Optional

from .models import ProjectConfig

if sys.version_info >= (3, 11):
    import tomllib
else:
    try:
        import tomllib
    except ImportError:
        try:
            import tomli as tomllib
        except ImportError:
            raise ImportError(
                "Python < 3.11 requires 'tomllib' backport: pip install tomli"
            )

DEFAULT_TIER_MAP = {
    "small": "qwen/qwen3-8b",
    "medium": "qwen/qwen3-14b",
    "large": "qwen/qwen3-235b-a22b",
}

DEFAULT_TASK_TIERS = {
    "summarize": "small",
    "extract": "small",
    "classify": "small",
    "generate": "medium",
    "synthesize": "medium",
    "code": "medium",
    "reason": "large",
    "research": "large",
}

_session_overrides: dict[str, str] = {}


def get_api_key() -> str:
    key = os.environ.get("OPENROUTER_API_KEY", "")
    if not key:
        raise EnvironmentError("OPENROUTER_API_KEY environment variable is not set")
    return key


def _find_toml(start: Path) -> Optional[Path]:
    current = start.resolve()
    while True:
        candidate = current / "llmgate.toml"
        if candidate.exists():
            return candidate
        parent = current.parent
        if parent == current:
            break
        current = parent
    return None


def _user_default_toml() -> Optional[Path]:
    p = Path.home() / ".config" / "llmgate" / "default.toml"
    return p if p.exists() else None


def load_config(project_id: str, start_dir: Optional[str] = None) -> ProjectConfig:
    search_start = Path(start_dir) if start_dir else Path.cwd()
    toml_path = _find_toml(search_start) or _user_default_toml()

    raw: dict = {}
    if toml_path:
        with open(toml_path, "rb") as f:
            raw = tomllib.load(f)

    project_section = raw.get("project", {})
    pid = project_section.get("id", project_id)
    db_path = project_section.get("db_path", f"./{pid}_llmgate.db")
    monthly_budget = project_section.get("monthly_budget_usd", 5.0)
    system_prompt = project_section.get("system_prompt", None)

    tiers_section = raw.get("tiers", {})
    model_tiers = {**DEFAULT_TIER_MAP, **tiers_section}

    task_tiers_section = raw.get("task_tiers", {})
    task_tiers = {**DEFAULT_TASK_TIERS, **task_tiers_section}

    tier_override = _session_overrides.get(project_id)

    return ProjectConfig(
        project_id=pid,
        db_path=str(db_path),
        monthly_budget_usd=monthly_budget,
        tier_override=tier_override,
        system_prompt=system_prompt,
        model_tiers=model_tiers,
        task_tiers=task_tiers,
    )


def set_session_tier(project_id: str, tier: str) -> None:
    valid = {"small", "medium", "large"}
    if tier not in valid:
        raise ValueError(f"tier must be one of {valid}, got {tier!r}")
    _session_overrides[project_id] = tier
