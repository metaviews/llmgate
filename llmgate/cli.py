import argparse
import sys


def cmd_stats(args: argparse.Namespace) -> None:
    from .config import load_config
    from . import stats as stats_module

    config = load_config(args.project)
    print(stats_module.summary(config.db_path, args.project, period=args.period))


def cmd_ask(args: argparse.Namespace) -> None:
    from .llmgate import ask

    result = ask(
        prompt=args.prompt,
        project_id=args.project,
        task_hint=args.task or None,
    )
    print(result["content"])
    print(
        f"\n[{result['tier']} | {result['model']} | "
        f"{result['input_tokens']}+{result['output_tokens']} tok | "
        f"${result['cost_usd']:.6f} | {result['latency_ms']}ms]",
        file=sys.stderr,
    )


def cmd_models(args: argparse.Namespace) -> None:
    from .config import load_config, DEFAULT_TIER_MAP

    project_id = args.project or "default"
    try:
        config = load_config(project_id)
        model_tiers = {**DEFAULT_TIER_MAP, **config.model_tiers}
    except Exception:
        model_tiers = DEFAULT_TIER_MAP

    for tier, model in model_tiers.items():
        print(f"{tier:8s}  {model}")


def cmd_budget(args: argparse.Namespace) -> None:
    from .config import load_config
    from .ledger import get_spend_this_month

    config = load_config(args.project)
    spend = get_spend_this_month(config.db_path, args.project)
    pct = spend / config.monthly_budget_usd * 100 if config.monthly_budget_usd else 0
    print(
        f"Project: {args.project}\n"
        f"Spent this month: ${spend:.6f}\n"
        f"Monthly budget:   ${config.monthly_budget_usd:.2f}\n"
        f"Used: {pct:.1f}%"
    )


def main() -> None:
    parser = argparse.ArgumentParser(prog="llmgate", description="LLM routing and usage tracking")
    sub = parser.add_subparsers(dest="command")

    p_stats = sub.add_parser("stats", help="Print usage summary")
    p_stats.add_argument("--project", required=True)
    p_stats.add_argument("--period", default="month", choices=["day", "week", "month", "all"])

    p_ask = sub.add_parser("ask", help="One-off prompt call")
    p_ask.add_argument("--project", required=True)
    p_ask.add_argument("--prompt", required=True)
    p_ask.add_argument("--task", default=None)

    p_models = sub.add_parser("models", help="Print tier->model mapping")
    p_models.add_argument("--project", default=None)

    p_budget = sub.add_parser("budget", help="Print spend vs ceiling")
    p_budget.add_argument("--project", required=True)

    args = parser.parse_args()

    if args.command == "stats":
        cmd_stats(args)
    elif args.command == "ask":
        cmd_ask(args)
    elif args.command == "models":
        cmd_models(args)
    elif args.command == "budget":
        cmd_budget(args)
    else:
        parser.print_help()
        sys.exit(1)
