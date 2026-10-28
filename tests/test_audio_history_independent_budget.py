import pytest
from test_studio_asset_query import rig
from test_studio_workspace_identity_history_contract import audio_history
from app.creative.asset_usage_budget import current_usage_budget

def test_binary_read_charges_active_request_budget(audio_history, monkeypatch):
    e = audio_history
    observed = []
    original = e.rig.assets._verified_bounded_content
    def observe(meta, maximum, guard):
        budget = current_usage_budget()
        assert budget is not None
        before = budget.read_bytes
        result = original(meta, maximum, guard)
        observed.append((budget.read_bytes - before, len(result)))
        return result
    monkeypatch.setattr(e.rig.assets, '_verified_bounded_content', observe)
    response = e.client.get(e.base + '/assets/' + e.asset['id'] + '/history', headers=e.headers)
    assert response.status_code == 200, response.text
    assert observed and observed[-1][0] >= observed[-1][1], observed
