import os
import tempfile
from datetime import datetime

import pytest

from llmgate.ledger import init_db, log_call, get_recent_calls, get_spend_this_month
from llmgate.models import CallRecord


def _record(**kwargs) -> CallRecord:
    defaults = dict(
        project_id="proj",
        task_type="summarize",
        tier="small",
        model="qwen/qwen3-8b",
        input_tokens=100,
        output_tokens=50,
        cost_usd=0.001,
        latency_ms=200,
        success=True,
        escalated=False,
        confidence=None,
        error_code=None,
        timestamp=datetime.utcnow(),
        prompt_fingerprint="abc123",
    )
    defaults.update(kwargs)
    return CallRecord(**defaults)


@pytest.fixture
def tmp_db(tmp_path):
    return str(tmp_path / "test.db")


def test_init_db_creates_tables(tmp_db):
    init_db(tmp_db)
    assert os.path.exists(tmp_db)


def test_log_call_and_retrieve(tmp_db):
    init_db(tmp_db)
    log_call(tmp_db, _record())
    calls = get_recent_calls(tmp_db, "proj", n=10)
    assert len(calls) == 1
    assert calls[0]["task_type"] == "summarize"


def test_get_recent_calls_limit(tmp_db):
    init_db(tmp_db)
    for _ in range(5):
        log_call(tmp_db, _record())
    calls = get_recent_calls(tmp_db, "proj", n=3)
    assert len(calls) == 3


def test_get_spend_this_month_sums(tmp_db):
    init_db(tmp_db)
    log_call(tmp_db, _record(cost_usd=0.01))
    log_call(tmp_db, _record(cost_usd=0.02))
    spend = get_spend_this_month(tmp_db, "proj")
    assert abs(spend - 0.03) < 1e-9


def test_get_spend_ignores_other_project(tmp_db):
    init_db(tmp_db)
    log_call(tmp_db, _record(cost_usd=0.05, project_id="other"))
    spend = get_spend_this_month(tmp_db, "proj")
    assert spend == 0.0


def test_get_spend_ignores_previous_months(tmp_db):
    init_db(tmp_db)
    old = _record(cost_usd=0.99, timestamp=datetime(2020, 1, 15))
    log_call(tmp_db, old)
    spend = get_spend_this_month(tmp_db, "proj")
    assert spend == 0.0


def test_empty_db_recent_calls(tmp_db):
    init_db(tmp_db)
    calls = get_recent_calls(tmp_db, "proj")
    assert calls == []


def test_missing_db_returns_zero_spend():
    spend = get_spend_this_month("/nonexistent/path/test.db", "proj")
    assert spend == 0.0
