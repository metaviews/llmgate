import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any


def _connect(db_path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def _period_start(period: str) -> str:
    now = datetime.utcnow()
    if period == "day":
        start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    elif period == "week":
        start = now - timedelta(days=now.weekday())
        start = start.replace(hour=0, minute=0, second=0, microsecond=0)
    elif period == "month":
        start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    else:
        return "1970-01-01"
    return start.isoformat()


def _fetch(db_path: str, project_id: str, period: str) -> list[dict[str, Any]]:
    if not Path(db_path).exists():
        return []
    start = _period_start(period)
    try:
        with _connect(db_path) as conn:
            rows = conn.execute(
                "SELECT * FROM calls WHERE project_id = ? AND timestamp >= ?",
                (project_id, start),
            ).fetchall()
            return [dict(r) for r in rows]
    except sqlite3.OperationalError:
        return []


def summary(db_path: str, project_id: str, period: str = "month") -> str:
    rows = _fetch(db_path, project_id, period)
    if not rows:
        return f"## llmgate stats: {project_id} ({period})\n\nNo data.\n"

    total = len(rows)
    successes = sum(1 for r in rows if r["success"])
    total_input = sum(r["input_tokens"] for r in rows)
    total_output = sum(r["output_tokens"] for r in rows)
    total_cost = sum(r["cost_usd"] for r in rows)
    escalations = sum(1 for r in rows if r["escalated"])

    tier_calls: dict[str, int] = {}
    tier_cost: dict[str, float] = {}
    tier_latency: dict[str, list[int]] = {}
    for r in rows:
        t = r["tier"]
        tier_calls[t] = tier_calls.get(t, 0) + 1
        tier_cost[t] = tier_cost.get(t, 0.0) + r["cost_usd"]
        tier_latency.setdefault(t, []).append(r["latency_ms"])

    task_calls: dict[str, int] = {}
    for r in rows:
        tt = r["task_type"]
        task_calls[tt] = task_calls.get(tt, 0) + 1

    lines = [
        f"## llmgate stats: {project_id} ({period})",
        "",
        f"- **Total calls:** {total}",
        f"- **Success rate:** {successes/total*100:.1f}%",
        f"- **Total tokens:** {total_input + total_output:,} "
        f"(input: {total_input:,}, output: {total_output:,})",
        f"- **Total cost:** ${total_cost:.6f}",
        f"- **Escalation rate:** {escalations/total*100:.1f}%",
        "",
        "### By tier",
    ]
    for tier in ("small", "medium", "large"):
        if tier not in tier_calls:
            continue
        c = tier_calls[tier]
        co = tier_cost[tier]
        avg_lat = sum(tier_latency[tier]) / len(tier_latency[tier])
        lines.append(
            f"- **{tier}:** {c} calls ({c/total*100:.0f}%), "
            f"${co:.6f} ({co/total_cost*100:.0f}% cost), "
            f"avg latency {avg_lat:.0f}ms"
        )

    lines.append("")
    lines.append("### By task type")
    for tt, c in sorted(task_calls.items(), key=lambda x: -x[1]):
        lines.append(f"- **{tt}:** {c} calls ({c/total*100:.0f}%)")

    return "\n".join(lines) + "\n"


def cost_trend(db_path: str, project_id: str, days: int = 30) -> str:
    if not Path(db_path).exists():
        return "No data.\n"
    start = (datetime.utcnow() - timedelta(days=days)).isoformat()
    try:
        with _connect(db_path) as conn:
            rows = conn.execute(
                """
                SELECT date(timestamp) as day, SUM(cost_usd) as total
                FROM calls
                WHERE project_id = ? AND timestamp >= ?
                GROUP BY day ORDER BY day
                """,
                (project_id, start),
            ).fetchall()
    except sqlite3.OperationalError:
        return "No data.\n"

    if not rows:
        return "No data.\n"

    max_cost = max(r["total"] for r in rows)
    bar_width = 30
    lines = [f"## Cost trend: {project_id} (last {days} days)", ""]
    for r in rows:
        bar_len = int(r["total"] / max_cost * bar_width) if max_cost > 0 else 0
        bar = "#" * bar_len
        lines.append(f"{r['day']}  {bar:<{bar_width}}  ${r['total']:.6f}")
    return "\n".join(lines) + "\n"


def model_performance(db_path: str, project_id: str) -> str:
    if not Path(db_path).exists():
        return "No data.\n"
    try:
        with _connect(db_path) as conn:
            rows = conn.execute(
                """
                SELECT model,
                       COUNT(*) as calls,
                       AVG(latency_ms) as avg_latency,
                       AVG(success) as success_rate,
                       AVG(cost_usd) as avg_cost
                FROM calls
                WHERE project_id = ?
                GROUP BY model
                ORDER BY calls DESC
                """,
                (project_id,),
            ).fetchall()
    except sqlite3.OperationalError:
        return "No data.\n"

    if not rows:
        return "No data.\n"

    lines = [f"## Model performance: {project_id}", ""]
    for r in rows:
        lines.append(
            f"- **{r['model']}:** {r['calls']} calls, "
            f"avg latency {r['avg_latency']:.0f}ms, "
            f"success {r['success_rate']*100:.1f}%, "
            f"avg cost ${r['avg_cost']:.6f}"
        )
    return "\n".join(lines) + "\n"


def flagged_loops(db_path: str, project_id: str, threshold: int = 5) -> str:
    if not Path(db_path).exists():
        return "No data.\n"
    try:
        with _connect(db_path) as conn:
            rows = conn.execute(
                """
                SELECT prompt_fingerprint, COUNT(*) as cnt
                FROM calls
                WHERE project_id = ? AND prompt_fingerprint IS NOT NULL
                GROUP BY prompt_fingerprint
                HAVING cnt >= ?
                ORDER BY cnt DESC
                """,
                (project_id, threshold),
            ).fetchall()
    except sqlite3.OperationalError:
        return "No data.\n"

    if not rows:
        return f"## Flagged loops: {project_id}\n\nNone detected.\n"

    lines = [f"## Flagged loops: {project_id}", ""]
    for r in rows:
        lines.append(f"- `{r['prompt_fingerprint']}`: {r['cnt']} calls")
    return "\n".join(lines) + "\n"
