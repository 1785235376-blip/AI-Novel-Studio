"""Studio production job cost truthfulness: explicit UNKNOWN, never fabricated.

The current candidate has no trusted provider usage/price/task-linkage contract
for IMAGE/VIDEO/AUDIO/Timeline production jobs, so every job view must expose an
explicit unknown cost object instead of omitting cost or implying zero. These are
pure projection tests: no provider/model is called.
"""
from __future__ import annotations

import pytest

from app.creative.production_execution import ProductionExecutionService

pytestmark = pytest.mark.file_backend_only


def job(owner):
    return {"id": "job-1", "novel_id": "novel-1", "branch_id": None, "version": 1,
            "status": "QUEUED", "context": {"command": None}, "measured": None}


@pytest.mark.parametrize("owner", ["image", "audio", "video", "timeline"])
def test_every_production_job_view_reports_explicit_unknown_cost(owner):
    view = ProductionExecutionService.view(job(owner), owner)
    assert view["contract"] == "studio-production-job/1"
    cost = view["cost"]
    assert cost["contract"] == "studio-job-cost/1"
    assert cost["state"] == "UNKNOWN"
    assert cost["currency"] is None
    assert cost["estimated_microusd"] is None
    assert cost["actual_microusd"] is None
    assert cost["accounted_microusd"] is None
    assert cost["trusted"] is False and cost["fabricated"] is False
    assert cost["linkage"] == "NONE"
    assert cost["reason"] == "PROVIDER_USAGE_PRICE_TASK_LINKAGE_NOT_INTEGRATED"
    assert cost["decision_required"] is True


def test_cost_projection_is_isolated_per_view():
    first = ProductionExecutionService.view(job("image"), "image")
    first["cost"]["state"] = "MUTATED"
    second = ProductionExecutionService.view(job("image"), "image")
    assert second["cost"]["state"] == "UNKNOWN"
    assert ProductionExecutionService.JOB_COST_CONTRACT["state"] == "UNKNOWN"


def test_job_view_does_not_invent_numeric_cost():
    for owner in ("image", "audio", "video", "timeline"):
        cost = ProductionExecutionService.view(job(owner), owner)["cost"]
        for key in ("estimated_microusd", "actual_microusd", "accounted_microusd"):
            assert cost[key] is None
        assert isinstance(cost["trusted"], bool) and cost["trusted"] is False
