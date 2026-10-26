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


def graph_create(e, count=1, request_id="usage-graph"):
    pin = {"asset_id": e.asset["id"], "version": e.asset["version"],
           "digest": e.asset["sha256"], "kind": "audio"}
    body = {"request_id": request_id, "definition": {"title": "Synthetic direct references",
        "nodes": [{"id": f"ref-{i:04d}", "definition_id": "asset_reference", "parameters": pin}
                  for i in range(count)]}}
    return checked(e.client.post(e.graph_url, headers=e.headers, json=body), 201)


def snapshot(root):
    return {str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in root.rglob("*") if p.is_file()}
