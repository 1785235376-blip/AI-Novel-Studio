"""Synthetic mixed-incarnation owner document: no historical presence leaks."""
import copy
from uuid import uuid4

from app.experimental.audio_scope_snapshot import inspect_existing_audio_scope
from test_audio_history_status_readonly import snapshot
from test_audio_shared_replacement_plan_independent import candidate
from test_studio_asset_query import rig


def test_old_rows_cannot_change_current_authority_observation(rig):
    project = rig.workspace.store
    current = project.incarnation(rig.nid)
    old = 'file:' + str(uuid4())
    outputs = []
    raw_versions = []
    for count in (1, 2):
        with project.store.transaction(rig.nid, rig.scope) as doc:
            # CreativeProjectStore explicitly filters these by incarnation;
            # audio rows have no incarnation binding in the original owner.
            doc['collections']['creative_documents_v2'] = {
                'current': {'project_incarnation': current},
                'old': {'project_incarnation': old},
            }
            rows = {}
            for i in range(count):
                item = candidate()
                item.update(novel_id=rig.nid, scope=copy.deepcopy(rig.scope), id='old-audio-' + str(i))
                rows[item['id']] = item
            doc['collections']['audio_v2_mix_proposals'] = rows
        raw_versions.append(project.store.path(rig.nid, rig.scope).read_bytes())
        before = snapshot(rig.root)
        outputs.append(inspect_existing_audio_scope(project, rig.nid, rig.scope, lambda: None))
        assert snapshot(rig.root) == before
    assert raw_versions[0] != raw_versions[1]
    assert outputs[0] == outputs[1]
    assert outputs[0]['audio_row_binding'] == 'UNVERIFIED'
    assert outputs[0]['project_charge_known'] is False
    assert 'document_sha256' not in outputs[0]
    assert 'observed_audio_field_bytes' not in outputs[0]
