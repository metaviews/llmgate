from llmgate.classifier import classify


def test_short_prompt_low_complexity():
    task, complexity = classify("Summarize this text.")
    assert task == "summarize"
    assert complexity == "low"


def test_long_reasoning_prompt_high_complexity():
    prompt = "Why " + "x" * 2100
    task, complexity = classify(prompt)
    assert task == "reason"
    assert complexity == "high"


def test_code_block_in_prompt():
    prompt = "Fix this bug:\n```python\ndef foo():\n    pass\n```"
    task, complexity = classify(prompt)
    assert task == "code"


def test_task_hint_overrides_type_not_complexity():
    prompt = "x" * 50  # short
    task, complexity = classify(prompt, task_hint="summarize")
    assert task == "summarize"
    assert complexity == "low"


def test_task_hint_with_long_prompt_stays_high():
    prompt = "x" * 2500
    task, complexity = classify(prompt, task_hint="summarize")
    assert task == "summarize"
    assert complexity == "high"


def test_extract_signals():
    task, _ = classify("List all the authors mentioned in the document.")
    assert task == "extract"


def test_reason_keywords():
    task, _ = classify("Explain why the system failed.")
    assert task == "reason"


def test_generate_fallback():
    task, _ = classify("Write a haiku about autumn leaves falling slowly.")
    assert task == "generate"


def test_chain_of_thought_forces_high():
    task, complexity = classify("Summarize step by step.")
    assert complexity == "high"
