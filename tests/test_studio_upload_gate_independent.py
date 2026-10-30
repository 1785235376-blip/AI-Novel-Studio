"""Independent HTTP checks of the closed manual import gate."""
import base64

import pytest

from test_audio_history_status_readonly import snapshot
from test_studio_asset_query import rig, shared_scope
from test_studio_workspace_identity_history_contract import audio_history

pytestmark = pytest.mark.file_backend_only


@pytest.mark.parametrize('prefix', ['/api', '/api/v1'])
@pytest.mark.parametrize('kind', ['audio', 'image'])
def test_gate_precedes_persistence_and_old_download_remains(audio_history, prefix, kind):
    e = audio_history
    body = {'filename': 'synthetic.wav' if kind == 'audio' else 'synthetic.png',
            'kind': kind, 'content_base64': base64.b64encode(e.content).decode(),
            'idempotency_key': 'independent-gate'}
    before = snapshot(e.rig.root)
    response = e.client.post(f'{prefix}/projects/{e.rig.nid}/studio/assets', json=body, headers=e.headers)
    assert response.status_code == 503, response.text
    assert response.json()['detail']['code'] == 'PROJECT_CAPACITY_WRITE_UNAVAILABLE'
    assert snapshot(e.rig.root) == before
    download = e.client.get(f"{prefix}/projects/{e.rig.nid}/studio/assets/{e.asset['id']}/download", headers=e.headers)
    assert download.status_code == 200 and download.content == e.content
    assert snapshot(e.rig.root) == before


@pytest.mark.parametrize('prefix', ['/api', '/api/v1'])
def test_revoked_or_unprivileged_actor_cannot_learn_capacity_gate(rig, prefix):
    scope, headers = shared_scope(rig)
    body = {'filename': 'synthetic.wav', 'kind': 'audio', 'content_base64': 'AA==',
            'idempotency_key': 'independent-auth'}
    path = f'{prefix}/projects/{rig.nid}/studio/assets'
    before = snapshot(rig.root)
    denied = rig.client.post(path, json=body, headers={**headers, 'X-Session-Token': 'token-no-grants'})
    assert denied.status_code == 403 and 'PROJECT_CAPACITY_WRITE_UNAVAILABLE' not in denied.text
    rig.sessions.revoke(headers['X-Session-Token'])
    revoked = rig.client.post(path, json=body, headers=headers)
    assert revoked.status_code in (401, 403) and 'PROJECT_CAPACITY_WRITE_UNAVAILABLE' not in revoked.text
    assert snapshot(rig.root) == before
