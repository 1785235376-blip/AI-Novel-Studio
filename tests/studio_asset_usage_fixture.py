"""Shared real File/main.app fixture for saved direct-reference observations.

All data are synthetic. Existing route authority and owner readers remain real.
"""
from copy import deepcopy
from types import SimpleNamespace
import hashlib

import pytest
from test_studio_asset_query import rig
from test_studio_workspace_identity_history_contract import audio_history, checked, create_timeline


@pytest.fixture
def usage_rig(audio_history, monkeypatch):
    from app.creative.graph import CreativeGraphService
    from app.experimental import api
    e = audio_history
    graph = CreativeGraphService(e.rig.workspace.store, e.rig.workspace)
    for name, value in graph.__dict__.items():
        monkeypatch.setattr(api.creative_graph_service, name, value, raising=False)
    e.graph = api.creative_graph_service
    e.actor = "local-author"
    e.graph_url = e.base + "/graphs"
    e.usage_base = f"/api/novels/{e.rig.nid}/experimental/production/assets/{e.asset['id']}"
    e.source = {"kind": "ASSET", "id": e.asset["id"], "version": e.asset["version"],
                "digest": e.asset["sha256"], "asset_kind": "audio"}
    return e


def graph_create(e, count=1, request_id="usage-graph", alternate=None):
    pin = {"asset_id": e.asset["id"], "version": e.asset["version"],
           "digest": e.asset["sha256"], "kind": "audio"}
    body = {"request_id": request_id, "definition": {"title": "Synthetic direct references",
        "nodes": [{"id": f"ref-{i:04d}", "definition_id": "asset_reference", "parameters": (alternate if alternate and i % 2 else pin)}
                  for i in range(count)]}}
    return checked(e.client.post(e.graph_url, headers=e.headers, json=body), 201)


def snapshot(root):
    return {str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in root.rglob("*") if p.is_file()}


def copied_graph_consumers(e, count=30, references=16, mixed=False):
    """Saved-schema synthetic scale fixture; >25 exceeds normal create capacity.

    Only fixture preparation bulk-copies the original owner record; every query
    still goes through the production reader and validates its original schema.
    """
    alternate = None
    if mixed:
        row = e.rig.seed('unrelated-image.png', 'image')
        alternate = {'asset_id': row['id'], 'version': row['version'], 'digest': row['sha256'], 'kind': 'image'}
    original = graph_create(e, references, 'scale-template', alternate)
    path = e.graph.store.path(e.rig.nid, e.rig.scope)
    import json
    state = json.loads(path.read_text(encoding='utf-8'))
    records = state['collections'][e.graph.GRAPHS]
    template = records.pop(original['id'])
    for i in range(count):
        row = deepcopy(template)
        row['id'] = f'synthetic-consumer-{i:04d}'
        records[row['id']] = row
    path.write_text(json.dumps(state), encoding='utf-8')
    return count * (references // 2 if mixed else references)


def copied_timeline_consumers(e, count=10, references=30):
    """Copy a real saved 30-clip Timeline after original HTTP schema validation."""
    import json
    original = create_timeline(e)
    value = deepcopy(original['timeline'])
    template = value['tracks'][0]['clips'][0]
    value['tracks'][0]['clips'] = [{**deepcopy(template), 'id': f'clip-{i:04d}'} for i in range(references)]
    url = e.base + '/production/timelines/' + original['id']
    saved = checked(e.client.put(url, headers=e.headers, json={
        'expected_version': original['version'], 'title': original['title'], 'timeline': value}))
    path = e.production.store.path(e.rig.nid, e.rig.scope)
    state = json.loads(path.read_text(encoding='utf-8'))
    records = state['collections']['creative_production_timelines_v2']
    template = records.pop(saved['id'])
    for i in range(count):
        row = deepcopy(template)
        row['id'] = f'synthetic-timeline-{i:04d}'
        records[row['id']] = row
    path.write_text(json.dumps(state), encoding='utf-8')
    return count * references

