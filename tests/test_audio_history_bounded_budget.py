"""The original guarded reader charges actual chunks to an active budget."""
import asyncio
import base64

import pytest

from app.creative.asset_usage_budget import UsageBudgetError, usage_read_budget
from app.services.asset_library_service import AssetLibraryService


@pytest.fixture
def stored(tmp_path):
    owner = AssetLibraryService(tmp_path)
    content = b'synthetic-' * 12000
    row = owner.create('synthetic-project', 'sound.wav', base64.b64encode(content).decode(),
                       'audio/wav', 'audio')
    return owner, row, content


def test_exact_budget_allows_native_read_and_counts_actual_bytes(stored):
    owner, row, content = stored
    with usage_read_budget(fresh=True) as budget:
        budget.MAX_READ_BYTES = len(content)
        assert owner._verified_bounded_content(row, owner.MAX_BYTES, lambda: None) == content
        assert (budget.reads, budget.read_bytes) == (1, len(content))


def test_budget_preflight_refuses_before_read_and_counts_attempt(stored):
    owner, row, content = stored
    with usage_read_budget(fresh=True) as budget:
        budget.MAX_READ_BYTES = len(content) - 1
        with pytest.raises(UsageBudgetError):
            owner._verified_bounded_content(row, owner.MAX_BYTES, lambda: None)
        assert (budget.reads, budget.read_bytes) == (1, 0)


def test_cancellation_after_chunk_keeps_attempt_and_actual_bytes(stored):
    owner, row, content = stored
    with usage_read_budget(fresh=True) as budget:
        def guard():
            if budget.read_bytes:
                raise asyncio.CancelledError()
        with pytest.raises(asyncio.CancelledError):
            owner._verified_bounded_content(row, owner.MAX_BYTES, guard)
        assert budget.reads == 1
        assert budget.read_bytes == min(65536, len(content))
        prior_bytes = budget.read_bytes
        assert owner._verified_bounded_content(row, owner.MAX_BYTES, lambda: None) == content
        assert (budget.reads, budget.read_bytes) == (2, prior_bytes + len(content))


def test_budget_reduced_during_guard_stops_before_next_chunk(stored):
    owner, row, content = stored
    with usage_read_budget(fresh=True) as budget:
        def guard():
            if budget.read_bytes:
                budget.MAX_READ_BYTES = budget.read_bytes
        with pytest.raises(UsageBudgetError):
            owner._verified_bounded_content(row, owner.MAX_BYTES, guard)
        assert budget.reads == 1
        assert budget.read_bytes == min(65536, len(content))
