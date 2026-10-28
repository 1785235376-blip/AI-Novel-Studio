import asyncio
import pytest
from test_studio_asset_query import rig
from test_studio_workspace_identity_history_contract import audio_history
from app.creative.asset_usage_budget import current_usage_budget, UsageReadBudget

def target(e):
    return e.base + '/assets/' + e.asset['id'] + '/history'

def test_native_byte_budget_rejects_before_binary_read(audio_history, monkeypatch):
    e = audio_history
    original = e.rig.assets._verified_bounded_content
    measured = []
    def limited(meta, maximum, guard):
        budget = current_usage_budget()
        budget.MAX_READ_BYTES = budget.read_bytes + len(e.content) - 1
        try:
            return original(meta, maximum, guard)
        finally:
            measured.append(budget.read_bytes)
    monkeypatch.setattr(e.rig.assets, '_verified_bounded_content', limited)
    response = e.client.get(target(e), headers=e.headers)
    assert response.status_code == 409, response.text
    assert 'UNCAPTURED' not in response.text
    assert measured

def test_native_read_attempt_limit_fails_closed(audio_history, monkeypatch):
    e = audio_history
    original = UsageReadBudget.begin_bounded_binary
    attempts = []
    def limited(self, size):
        before = self.reads
        self.MAX_READS = before
        try:
            return original(self, size)
        finally:
            attempts.append((before, self.reads))
    monkeypatch.setattr(UsageReadBudget, 'begin_bounded_binary', limited)
    response = e.client.get(target(e), headers=e.headers)
    assert response.status_code == 409, response.text
    assert 'UNCAPTURED' not in response.text
    assert len(attempts) == 1 and attempts[0][1] == attempts[0][0] + 1

def test_http_native_cancel_after_actual_chunk(audio_history, monkeypatch):
    e = audio_history
    original = e.rig.assets._verified_bounded_content
    observed = []
    def wrapped(meta, maximum, guard):
        budget = current_usage_budget()
        start = budget.read_bytes
        def cancel_after_binary():
            if budget.read_bytes - start >= len(e.content):
                observed.append((budget.reads, budget.read_bytes - start))
                raise asyncio.CancelledError()
            guard()
        return original(meta, maximum, cancel_after_binary)
    monkeypatch.setattr(e.rig.assets, '_verified_bounded_content', wrapped)
    with pytest.raises(RuntimeError, match='No response returned'):
        e.client.get(target(e), headers=e.headers)
    assert observed and observed[0][1] >= len(e.content)

def test_original_native_reader_without_budget(audio_history):
    e = audio_history
    assert current_usage_budget() is None
    with e.rig.workspace._asset_scope(e.rig.nid, e.rig.scope):
        assert e.rig.assets.content(e.asset['id'], max_bytes=e.rig.assets.MAX_BYTES) == e.content
