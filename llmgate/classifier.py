_VALID_TASK_TYPES = {
    "summarize", "extract", "classify", "generate",
    "synthesize", "code", "reason", "research",
}

_CODE_SIGNALS = {"```", "def ", "function", "import ", "class ", "bug", "error:", "traceback"}
_EXTRACT_SIGNALS = {"extract", "list all", "identify all", "find every", "what are the"}
_SUMMARIZE_SIGNALS = {"summarize", "summary", "tldr", "brief", "condense", "shorten"}
_REASON_SIGNALS = {"why", "explain", "analyze", "evaluate", "compare", "assess", "argue", "critique"}
_SYNTHESIZE_SIGNALS = {"synthesize", "combine", "integrate", "across", "patterns", "themes"}

_HIGH_COMPLEXITY_TASKS = {"reason", "synthesize", "research"}
_LOW_COMPLEXITY_TASKS = {"summarize", "extract", "classify"}


def classify(prompt: str, task_hint: str | None = None) -> tuple[str, str]:
    p_lower = prompt.lower()

    if task_hint and task_hint in _VALID_TASK_TYPES:
        task_type = task_hint
    elif any(sig in p_lower for sig in _CODE_SIGNALS):
        task_type = "code"
    elif any(sig in p_lower for sig in _EXTRACT_SIGNALS):
        task_type = "extract"
    elif any(sig in p_lower for sig in _SUMMARIZE_SIGNALS):
        task_type = "summarize"
    elif any(sig in p_lower for sig in _REASON_SIGNALS):
        task_type = "reason"
    elif any(sig in p_lower for sig in _SYNTHESIZE_SIGNALS):
        task_type = "synthesize"
    else:
        task_type = "generate"

    complexity = _classify_complexity(prompt, p_lower, task_type)
    return task_type, complexity


def _classify_complexity(prompt: str, p_lower: str, task_type: str) -> str:
    if (
        len(prompt) > 2000
        or "step by step" in p_lower
        or "chain of thought" in p_lower
        or task_type in _HIGH_COMPLEXITY_TASKS
    ):
        return "high"
    if len(prompt) < 400 and task_type in _LOW_COMPLEXITY_TASKS:
        return "low"
    return "medium"
