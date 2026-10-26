"""Independent resource counterexamples over synthetic files and mounted owners.

Preparation may mutate synthetic fixtures. Query assertions never replace an
authorization decision, never depend on timing sleeps, and never invoke models.
"""
from copy import deepcopy
import hashlib
import json
from pathlib import Path

import pytest

from studio_asset_usage_fixture import (
    usage_rig, audio_history, rig, graph_create, create_timeline, snapshot,
    copied_graph_consumers, copied_timeline_consumers,
)
from studio_asset_usage_meter import ReadMeter
from test_studio_asset_usage_independent import query, page, refused

pytestmark = pytest.mark.file_backend_only


def complete_snapshot(root):
    """Include directories and files, so zero-byte locks cannot disappear."""
    return {str(p.relative_to(root)): ("directory" if p.is_dir() else
            hashlib.sha256(p.read_bytes()).hexdigest()) for p in root.rglob("*")}


@pytest.mark.parametrize("kind", ["depth", "string", "number", "objects"])
def test_independent_parser_preflight_refuses_before_json_loads(tmp_path, monkeypatch, kind):
    from app.creative.asset_usage_budget import UsageReadBudget, UsageBudgetError
    budget = UsageReadBudget()
    if kind == "depth":
        data = b"[" * (budget.MAX_JSON_DEPTH + 1) + b"0" + b"]" * (budget.MAX_JSON_DEPTH + 1)
    elif kind == "string":
        data = b'{"private":"' + b"x" * (budget.MAX_JSON_STRING_BYTES + 1) + b'"}'
    elif kind == "number":
        data = b"[" + b"1" * (budget.MAX_JSON_NUMBER_BYTES + 1) + b"]"
    else:
        # Many tiny dicts are cheap encoded input with expensive object overhead.
        data = b"[" + b",".join([b"{}"] * (budget.MAX_JSON_TOKENS + 1)) + b"]"
    assert len(data) < budget.MAX_SCOPE_BYTES
    target = tmp_path / "hostile.json"
    target.write_bytes(data)
    decoded = []
    original = json.loads
    def loads(value, *args, **kwargs):
        decoded.append(value)
        return original(value, *args, **kwargs)
    monkeypatch.setattr(json, "loads", loads)
    with pytest.raises(UsageBudgetError):
        budget.read(target)
    assert decoded == [], "hostile document reached allocating JSON parser"
    assert budget.read_bytes <= budget.MAX_READ_BYTES


@pytest.mark.parametrize("stage,change", [
    ("before_open", "grow"), ("before_open", "replace"),
    ("after_chunk", "grow"), ("after_chunk", "same-size-write"),
])
def test_independent_file_changes_are_refused_at_deterministic_read_boundaries(tmp_path, monkeypatch, stage, change):
    from app.creative import asset_usage_budget as module
    target = tmp_path / "changing.json"
    target.write_bytes(b'"' + b"a" * (module.UsageReadBudget.READ_CHUNK_BYTES * 2) + b'"')
    budget = module.UsageReadBudget()
    fired = []
    def hook(observed, path):
        if observed != stage or Path(path) != target or fired:
            return
        fired.append(observed)
        if change == "grow":
            with target.open("ab") as handle:
                handle.write(b" " * budget.MAX_SCOPE_BYTES)
        elif change == "replace":
            replacement = tmp_path / "replacement.json"
            replacement.write_bytes(target.read_bytes())
            replacement.replace(target)
        else:
            with target.open("r+b") as handle:
                handle.seek(1)
                handle.write(b"Z")
    monkeypatch.setattr(module, "_read_checkpoint", hook)
    with pytest.raises(module.UsageBudgetError):
        budget.read(target)
    assert fired == [stage]
    assert budget.read_bytes <= budget.MAX_READ_BYTES


def test_independent_repeated_and_nested_reads_cannot_reset_cumulative_admission(tmp_path):
    from app.creative.asset_usage_budget import usage_read_budget, current_usage_budget, UsageBudgetError
    target = tmp_path / "repeat.json"
    target.write_text('{"n":1}', encoding="utf-8")
    assert current_usage_budget() is None
    with usage_read_budget() as first:
        first.MAX_READ_BYTES = target.stat().st_size * 2
        assert first.read(target) == '{"n":1}'
        with usage_read_budget() as nested:
            assert nested is first
            assert nested.read(target) == '{"n":1}'
        with pytest.raises(UsageBudgetError):
            first.read(target)
        assert first.read_bytes == target.stat().st_size * 2
    assert current_usage_budget() is None
    with usage_read_budget() as second:
        assert second is not first and second.read_bytes == second.reads == 0
        assert second.read(target) == '{"n":1}'


def test_independent_json_token_allowance_is_cumulative_across_decodes(tmp_path):
    from app.creative.asset_usage_budget import UsageReadBudget, UsageBudgetError
    target = tmp_path / "tokens.json"
    target.write_text("[1,2,3,4]", encoding="utf-8")
    budget = UsageReadBudget()
    budget.MAX_REQUEST_JSON_TOKENS = 8
    budget.read(target)
    with pytest.raises(UsageBudgetError):
        for _ in range(8):
            budget.read(target)
    assert budget.json_tokens <= budget.MAX_REQUEST_JSON_TOKENS


@pytest.mark.parametrize("owner", ["graph", "timeline", "asset"])
@pytest.mark.parametrize("phase", ["first", "continuation", "replay"])
def test_independent_http_budget_failure_never_returns_a_cached_or_empty_page(usage_rig, monkeypatch, owner, phase):
    from app.creative.asset_usage_budget import UsageReadBudget
    from app.creative import asset_usage_paging
    e = usage_rig
    graph_create(e, 3)
    create_timeline(e)
    create_timeline(e)
    monkeypatch.setattr(asset_usage_paging, "_tokens", {})
    params = {"limit": 1}
    if phase != "first":
        first = page(query(e, params, owner=owner))
        params["cursor"] = first["next_cursor"]
        if phase == "replay":
            assert page(query(e, params, owner=owner))["items"]
    before = complete_snapshot(e.rig.root)
    cached_before = deepcopy(asset_usage_paging._tokens)
    monkeypatch.setattr(UsageReadBudget, "MAX_READ_BYTES", 1)
    refused(query(e, params, owner=owner), e)
    assert complete_snapshot(e.rig.root) == before
    assert asset_usage_paging._tokens == cached_before


@pytest.mark.parametrize("kind", ["depth", "string", "objects", "oversize"])
def test_independent_http_hostile_scope_does_not_reach_scope_decoder(usage_rig, monkeypatch, kind):
    from app.creative.asset_usage_budget import UsageReadBudget
    e = usage_rig
    graph_create(e)
    target = e.graph.store.path(e.rig.nid, e.rig.scope)
    state = json.loads(target.read_text(encoding="utf-8"))
    if kind == "depth":
        value = 0
        for _ in range(UsageReadBudget.MAX_JSON_DEPTH + 1):
            value = [value]
        state["private-padding"] = value
    elif kind == "string":
        state["private-padding"] = "x" * (UsageReadBudget.MAX_JSON_STRING_BYTES + 1)
    elif kind == "objects":
        state["private-padding"] = [{} for _ in range(UsageReadBudget.MAX_JSON_TOKENS + 1)]
    else:
        state["private-padding"] = "x" * UsageReadBudget.MAX_SCOPE_BYTES
    payload = json.dumps(state)
    target.write_text(payload, encoding="utf-8")
    decoded = []
    original = json.loads
    def loads(value, *args, **kwargs):
        if isinstance(value, (str, bytes)) and ("private-padding" in value if isinstance(value, str) else b"private-padding" in value):
            decoded.append(True)
        return original(value, *args, **kwargs)
    monkeypatch.setattr(json, "loads", loads)
    refused(query(e, {"limit": 1}), e)
    assert decoded == [], "scope was decoded before the resource refusal"


@pytest.mark.parametrize("stage", ["after_source", "after_consumer", "before_return"])
def test_independent_reauthorization_uses_the_same_request_budget(usage_rig, monkeypatch, stage):
    from app.creative import asset_usage_paging
    from app.creative.asset_usage_budget import current_usage_budget
    e = usage_rig
    graph_create(e, 3)
    budgets, fired = [], []
    def checkpoint(observed):
        budget = current_usage_budget()
        if budget is not None:
            budgets.append(budget)
        if observed == stage and not fired:
            fired.append(stage)
            e.rig.sessions.revoke(e.headers["X-Session-Token"])
    monkeypatch.setattr(asset_usage_paging, "_checkpoint", checkpoint)
    response = query(e, {"limit": 1}, owner="asset")
    assert response.status_code == 401, response.text
    assert response.json()["code"] == "SESSION_REQUIRED"
    assert "items" not in response.json()
    assert fired == [stage] and budgets and all(budget is budgets[0] for budget in budgets)


@pytest.mark.parametrize("prefix", ["/api", "/api/v1"])
def test_independent_initialized_compat_query_preserves_540_positions_in_six_pages(usage_rig, monkeypatch, prefix):
    e = usage_rig
    assert copied_graph_consumers(e, count=30, references=16) + copied_timeline_consumers(e, count=2) == 540
    before = complete_snapshot(e.rig.root)
    found, cursor, pages = [], None, 0
    meter = ReadMeter(e.rig.root)
    with monkeypatch.context() as patch:
        meter.install(patch)
        while pages < 20:
            params = {"limit": 100}
            if cursor:
                params["cursor"] = cursor
            body = page(query(e, params, owner="asset", prefix=prefix))
            found.extend((item["owner"], item["id"], item.get("node_id", item.get("clip_id"))) for item in body["items"])
            pages += 1
            cursor = body["next_cursor"]
            if not body["has_more"]:
                assert body["total"] == 540 and cursor is None
                break
    assert pages == 6 and len(found) == len(set(found)) == 540
    assert complete_snapshot(e.rig.root) == before
    assert meter.write_calls == 0


def test_independent_compat_read_existing_lock_is_not_a_strict_mode(usage_rig, monkeypatch):
    """Record compatibility facts; this does not claim strict-readonly support."""
    e = usage_rig
    graph_create(e, 2)
    before = complete_snapshot(e.rig.root)
    meter = ReadMeter(e.rig.root)
    with monkeypatch.context() as patch:
        meter.install(patch)
        body = page(query(e, {"limit": 1}, owner="asset"))
    assert body["items"] and meter.write_calls == 0
    assert complete_snapshot(e.rig.root) == before
    # The original coordinator still opens lock handles in a writable mode.
    assert meter.write_opens > 0

