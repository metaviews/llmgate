# llmgate

Lightweight LLM routing, tiered model selection, and usage tracking for [OpenRouter](https://openrouter.ai). No server, no Docker, no Redis — pure Python + SQLite.

## Features

- **Automatic task classification** — detects task type (summarize, extract, reason, code, …) and complexity from the prompt
- **Tier-based routing** — maps tasks to `small` / `medium` / `large` model tiers
- **Per-project SQLite ledger** — every call logged with tokens, cost, latency
- **Budget guardrails** — monthly ceiling with automatic tier downgrade when limit is near
- **Stats surface** — markdown-formatted summaries, cost trends, loop detection

## Install

```bash
pip install -e /path/to/llmgate
```

Or from within the repo:

```bash
pip install -e .
```

Requires Python ≥ 3.10 and the `OPENROUTER_API_KEY` environment variable.

## 3-step integration into a new project

**Step 1** — Set the API key:

```bash
export OPENROUTER_API_KEY=sk-or-...
```

**Step 2** — Drop a `llmgate.toml` in your project root:

```toml
[project]
id = "myproject"
db_path = "./data/llmgate.db"
monthly_budget_usd = 10.0
system_prompt = "You are a helpful assistant."

[tiers]
small = "qwen/qwen3-8b"
medium = "qwen/qwen3-14b"
large = "qwen/qwen3-235b-a22b"

[task_tiers]
summarize = "small"
extract = "small"
generate = "medium"
reason = "large"
```

**Step 3** — Call `ask()`:

```python
from llmgate import llmgate

result = llmgate.ask(
    prompt="Summarize this document...",
    project_id="myproject",
)
print(result["content"])
```

## `llmgate.toml` format

| Key | Description | Default |
|-----|-------------|---------|
| `project.id` | Unique project identifier | required |
| `project.db_path` | Path to SQLite database file | `./{id}_llmgate.db` |
| `project.monthly_budget_usd` | Monthly spend ceiling in USD | `5.0` |
| `project.system_prompt` | Prepended to every call | none |
| `[tiers]` | Override `small`/`medium`/`large` model strings | see defaults |
| `[task_tiers]` | Override task → tier mapping | see defaults |

`llmgate.toml` is found by walking up from `cwd`, like git. Falls back to `~/.config/llmgate/default.toml`.

**Never put your API key in the TOML.** Use the `OPENROUTER_API_KEY` environment variable.

### Default tier map

| Tier | Model |
|------|-------|
| `small` | `qwen/qwen3-8b` |
| `medium` | `qwen/qwen3-14b` |
| `large` | `qwen/qwen3-235b-a22b` |

### Default task → tier map

| Task | Tier |
|------|------|
| `summarize` | small |
| `extract` | small |
| `classify` | small |
| `generate` | medium |
| `synthesize` | medium |
| `code` | medium |
| `reason` | large |
| `research` | large |

## `ask()` reference

```python
result = llmgate.ask(
    prompt="...",           # required
    project_id="...",       # required
    task_hint="summarize",  # optional: override task detection
    force_tier="small",     # optional: skip all routing logic
    start_dir="/my/proj",   # optional: where to search for llmgate.toml
)
```

**Returns:**

```python
{
    "content": "...",              # model response text
    "model": "qwen/qwen3-8b",     # actual model used
    "tier": "small",              # tier resolved
    "task_type": "summarize",     # detected or hinted task
    "input_tokens": 312,
    "output_tokens": 87,
    "cost_usd": 0.000024,
    "latency_ms": 840,
    "success": True,
    "escalated": False,           # True if tier was upgraded during retry
    "routing_reasoning": "...",   # human-readable routing explanation
}
```

## Other API functions

```python
# Markdown stats summary for a project
llmgate.stats(project_id="myproject", period="week")  # day|week|month|all

# Total cost today (float)
llmgate.cost_today(project_id="myproject")

# Override tier for the current Python session
llmgate.set_tier(project_id="myproject", tier="medium")
```

## CLI

```bash
# Print usage summary
llmgate stats --project myproject --period week

# One-off call
llmgate ask --project myproject --prompt "Explain quantum entanglement" --task reason

# Show tier->model mapping
llmgate models

# Show spend vs budget
llmgate budget --project myproject
```

## How routing works

1. **Classify** — heuristics detect `task_type` and `complexity` (low/medium/high) from the prompt text. No model call; instant and free.
2. **Resolve** — `task_type` maps to a base tier; `high` complexity upgrades `small→medium` and forces `reason`/`synthesize` to `large`.
3. **Budget check** — if monthly spend ≥ ceiling, tier is downgraded (`large→medium→small`). A warning is printed to stderr.
4. **Dispatch** — POST to OpenRouter with exponential-backoff retry (1s, 2s). After retries exhausted on 429/5xx, escalates to the next tier once.
5. **Log** — every call written to SQLite (WAL mode for concurrent safety).

## Running tests

```bash
pytest tests/ -v
```
