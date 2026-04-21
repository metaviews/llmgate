from dataclasses import dataclass, field
from typing import Optional
from datetime import datetime


@dataclass
class CallRecord:
    project_id: str
    task_type: str
    tier: str
    model: str
    input_tokens: int
    output_tokens: int
    cost_usd: float
    latency_ms: int
    success: bool
    escalated: bool
    confidence: Optional[float]
    error_code: Optional[str]
    timestamp: datetime = field(default_factory=datetime.utcnow)
    prompt_fingerprint: Optional[str] = None


@dataclass
class ProjectConfig:
    project_id: str
    db_path: str
    monthly_budget_usd: float = 5.0
    tier_override: Optional[str] = None
    system_prompt: Optional[str] = None
    model_tiers: dict = field(default_factory=dict)
    task_tiers: dict = field(default_factory=dict)


@dataclass
class RoutingDecision:
    task_type: str
    complexity: str
    tier: str
    model: str
    reasoning: str
