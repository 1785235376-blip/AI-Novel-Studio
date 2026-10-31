"""Coordinator probes on frozen product code, using synthetic owner transactions.

The original Graph API intentionally has no consumer-delete operation. These
fixtures inject saved-state removal/recreation through the original File store;
they do not add a product deletion API or delete assets.
"""
from copy import deepcopy

import pytest

from conftest import restore_global_settings
from studio_asset_usage_fixture import usage_rig, audio_history, rig, graph_create, snapshot
from test_studio_asset_usage_independent import query, page, refused


def remove_saved_consumer(e, gid, *, recreate=False):
    from app.creative.graph import GRAPHS
    with e.graph.store.transaction(e.rig.nid, e.rig.scope) as document:
        rows = document['collections'][GRAPHS]
        old = rows.pop(gid)
        if recreate:
            replacement = deepcopy(old)
            # Retain the pin, version and definition digest: a newly observed
            # creation identity still invalidates the continuation. Exact ABA
            # with every saved field restored is outside the declared guarantee.
            replacement['created_at'] = '2026-10-26T01:23:45+00:00'
            replacement['updated_at'] = replacement['created_at']
            rows[gid] = replacement


@pytest.mark.parametrize('recreate', [False, True])
def test_saved_consumer_removal_or_recreation_between_pages(usage_rig, recreate):
    e = usage_rig
    graph = graph_create(e, 3)
    first = page(query(e, {'limit': 1}))
    remove_saved_consumer(e, graph['id'], recreate=recreate)
    before = snapshot(e.rig.root)
    refused(query(e, {'limit': 1, 'cursor': first['next_cursor']}), e)
    assert snapshot(e.rig.root) == before


@pytest.mark.parametrize('stage', ['after_consumer', 'before_issue', 'before_return'])
def test_saved_consumer_removed_during_observation_is_refused(usage_rig, monkeypatch, stage):
    from app.creative import asset_usage_paging
    e = usage_rig
    graph = graph_create(e, 3)
    reached = []

    def checkpoint(value):
        if value == stage and not reached:
            reached.append(value)
            remove_saved_consumer(e, graph['id'])

    monkeypatch.setattr(asset_usage_paging, '_checkpoint', checkpoint)
    refused(query(e, {'limit': 1}), e)
    assert reached == [stage]


def test_postgres_explicit_paging_refuses_before_connect(usage_rig, monkeypatch):
    e = usage_rig
    graph_create(e, 3)
    reached = []

    def forbidden():
        reached.append(True)
        raise AssertionError('unbounded PostgreSQL reader was invoked')

    monkeypatch.setattr(e.graph.store, 'backend', 'postgres')
    monkeypatch.setattr(e.graph.store, '_connect', forbidden)
    refused(query(e, {'limit': 1}), e)
    assert reached == []
