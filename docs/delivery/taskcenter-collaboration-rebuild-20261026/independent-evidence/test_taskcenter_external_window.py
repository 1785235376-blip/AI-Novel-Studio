"""Additional independent source-owner/window probes on the same freeze."""
from copy import deepcopy
from test_taskcenter_external_adversarial import env, rig, read, first, restart, snap
import pytest
pytestmark=pytest.mark.file_backend_only

def test_source_document_replacement_same_payload_invalidates(env):
    e=env;token=first(e)
    collections=deepcopy(e.store.read(e.r.nid,e.scope)['collections'])
    e.store.path(e.r.nid,e.scope).unlink()
    with e.store.transaction(e.r.nid,e.scope) as d:d['collections']=collections
    before=snap(e.r.root)
    restart(read(e,token))
    assert read(e).status_code==200
    assert snap(e.r.root)==before

def test_unmatched_private_row_change_does_not_invalidate_filtered_window(env):
    e=env
    # Re-key actual HTTP-created rows through the original transaction writer.
    with e.store.transaction(e.r.nid,e.scope) as d:
        rows=d['collections']['team_runs']
        for i,row in enumerate(list(rows.values())):
            del rows[row['id']]
            row['id']=('visible-target-' + str(i)) if i<2 else 'private-other'
            rows[row['id']]=row
    response=read(e,q='visible-target-');assert response.status_code==200,response.text
    token=response.json()['next_cursor'];assert token
    with e.store.transaction(e.r.nid,e.scope) as d:
        d['collections']['team_runs']['private-other']['instruction']='unrelated private change'
    before=snap(e.r.root)
    response=read(e,token,q='visible-target-');assert response.status_code==200,response.text
    assert snap(e.r.root)==before
