"""Actual mounted File HTTP handoff; real authority and PNG bytes, no inference."""
import base64
import copy
import hashlib
import io
import json
from contextlib import contextmanager
from dataclasses import replace
from uuid import uuid4

import pytest
from PIL import Image

from app.actor_context import SessionContext
from app.creative.graph_asset_inputs import GraphAssetInputs
from app.services.comic_page_origin import FEATURES
from test_r3_mounted_contracts import mounted, prefix, checked, scoped
from test_v2_independent_workspace_api import client


@pytest.fixture
def handoff_http(client, monkeypatch):
    e = client
    monkeypatch.setenv('EXPERIMENTAL_FEATURES', ','.join(sorted(FEATURES | {'author_context_inspector_v2'})))
    e.host = 'comic-http-host-' + uuid4().hex
    e.sessions.register(e.host, SessionContext('session-' + e.host, 'client-' + e.host,
                                            'comic-http-author', 'comic-http-workspace'))
    e.headers = {'X-Session-Token': e.host}
    e.scope = {'mode': 'local', 'novel_id': e.nid}
    checked(e.client.post(e.studio_base + '/activate', headers=e.headers))
    e.production = e.experimental.studio_production_service
    monkeypatch.setattr(e.production, 'workspace', e.studio)
    monkeypatch.setattr(e.production, 'store', e.studio.store)
    monkeypatch.setattr(e.production, 'timeline_inputs', GraphAssetInputs(e.production))
    monkeypatch.setattr(e.production, 'comic_images', None)
    monkeypatch.setattr(e.production, 'comic_handoff', None)
    e.comic = e.experimental.comic_layouts_service
    monkeypatch.setattr(e.comic, 'independent_store', e.studio.store)
    # The original lease closure also reads this captured API dependency.
    # Use the fixture's real File repository, as the membership resolver does.
    monkeypatch.setattr(e.api, 'authorization_service', e.authorization)
    e.production.configure_comic(e.comic)
    e.comic_base = e.prefix + f'/novels/{e.nid}/experimental/comic-layouts'
    e.production_base = e.studio_base + '/production'
    e.handoff_base = e.production_base + '/comic-handoffs'
    return e


def approved_page(e, *, text=False):
    bubbles = ([{'id': 'b', 'kind': 'DIALOGUE', 'text': '原漫画文字', 'x': 50, 'y': 380,
                 'width': 200, 'height': 130, 'font_size': 24}] if text else [])
    row = checked(e.client.post(e.comic_base + '/records', headers=e.headers, json={
        'title': 'Synthetic HTTP page', 'source_mode': 'INDEPENDENT', 'preset': 'PAGE',
        'width': 320, 'height': 640, 'segment_height': 320,
        'panels': [{'id': 'p', 'artwork_mode': 'BLANK', 'order': 1, 'x': 24, 'y': 24,
                    'width': 264, 'height': 580, 'bubbles': bubbles}]}), 201)
    url = e.comic_base + '/records/' + row['id']
    report = checked(e.client.post(url + '/preflight', headers=e.headers, json={'expected_version': row['version']}))
    row = checked(e.client.post(url + '/approve', headers=e.headers, json={
        'expected_version': row['version'], 'review_digest': report['review_digest'], 'acknowledge_warnings': True}))
    return row, report['review_digest']


def request(pages):
    return {'title': 'HTTP static draft', 'width': 640, 'height': 360, 'fps': 24,
            'pages': [{'id': row['id'], 'version': row['version'], 'review_digest': digest, 'duration_ms': 10000}
                      for row, digest in pages]}


def intent(e, body, request_id='http-create'):
    preview = checked(e.client.post(e.handoff_base + '/preview', headers=e.headers, json=body))
    return {'request_id': request_id, 'request': body,
            'reviewed_preview_digest': preview['preview']['preview_digest'], 'acknowledge_losses': True}


def counts(e):
    state = e.store.read(e.nid, e.scope)['collections']
    return (len(list(e.assets.root.glob('*.bin'))), len(state.get('creative_production_timelines_v2', {})),
            len(state.get('comic_timeline_handoffs_v1', {})))


def private(response):
    assert response.headers['cache-control'] == 'no-store'
    assert response.headers['x-content-type-options'] == 'nosniff'


def rejected(response, status, code=None):
    assert response.status_code == status, response.text
    private(response)
    if code: assert response.json()['detail']['code'] == code
    assert 'private-canary' not in response.text


def routes(e, value):
    return [('POST', e.handoff_base + '/preview', value['request']),
            ('POST', e.handoff_base, value), ('GET', e.handoff_base + '/' + value['request_id'], None),
            ('POST', e.handoff_base + '/' + value['request_id'] + '/resume', {'expected_version': 1}),
            ('POST', e.handoff_base + '/' + value['request_id'] + '/cancel', {'expected_version': 1})]


def call(e, route, headers=None):
    method, path, body = route
    return e.client.request(method, path, headers=e.headers if headers is None else headers,
                            **({'json': body} if body is not None else {}))


def collaborative(e, monkeypatch):
    from app import dependencies
    from app.packaging.bootstrap_api import PackagedBootstrapRegistry
    from app.packaging.local_session_bootstrap import LocalSessionBootstrap, TrustedLocalIdentity
    from app.packaging.runtime_identity import RuntimeIdentity
    scoped(e, monkeypatch)
    config = replace(e.api.settings, enable_packaged_runtime=True, frontend_origin='http://127.0.0.1:4173')
    monkeypatch.setattr(e.api, 'settings', config)
    monkeypatch.setattr(e.main, 'settings', config)
    def actor_headers(actor):
        manager = LocalSessionBootstrap(runtime=RuntimeIdentity.create(), sessions=e.sessions,
            trusted_identity=TrustedLocalIdentity(actor, e.workspace), expected_origin=config.frontend_origin)
        token = manager.exchange(bootstrap_secret=manager.take_launcher_secret(),
            runtime_instance_id=manager.runtime.runtime_instance_id,
            origin=manager.expected_origin, remote_host='127.0.0.1').session_token
        registry = PackagedBootstrapRegistry(expected_origin=manager.expected_origin)
        registry.configure(manager)
        monkeypatch.setattr(e.main, 'packaged_bootstrap_registry', registry)
        monkeypatch.setattr(dependencies, 'packaged_bootstrap_registry', registry)
        return {'X-Session-Token': token, 'X-Branch-ID': e.branch}
    e.actor_headers = actor_headers
    e.headers = actor_headers(e.lead)
    checked(e.client.post(e.studio_base + '/activate', headers=e.headers))
    return e


def test_actual_http_preview_bytes_create_readback_and_original_timeline(handoff_http, tmp_path):
    e = handoff_http
    body = request([approved_page(e), approved_page(e, text=True)])
    before = copy.deepcopy(e.store.read(e.nid, e.scope))
    response = e.client.post(e.handoff_base + '/preview', headers=e.headers, json=body)
    data = checked(response); private(response)
    assert before == e.store.read(e.nid, e.scope) and counts(e) == (0, 0, 0)
    assert len(data['pages']) == len(data['preview']['pages']) == 2
    for index, (part, pin) in enumerate(zip(data['pages'], data['preview']['pages'])):
        pixels = base64.b64decode(part['png_base64'], validate=True)
        assert part['index'] == index and hashlib.sha256(pixels).hexdigest() == pin['png_sha256']
        with Image.open(io.BytesIO(pixels)) as image:
            image.load(); assert image.format == 'PNG' and image.size == (320, 640)
        (tmp_path / ('page-' + str(index) + '.png')).write_bytes(pixels)
    value = {'request_id': 'http-create', 'request': body,
             'reviewed_preview_digest': data['preview']['preview_digest'], 'acknowledge_losses': True}
    response = e.client.post(e.handoff_base, headers=e.headers, json=value)
    created = checked(response); private(response)
    assert created['status'] == 'DRAFT_CREATED' and counts(e) == (2, 1, 1)
    readback = checked(e.client.get(e.handoff_base + '/http-create', headers=e.headers))
    assert readback['timeline_snapshot'] == created['timeline_snapshot']
    original = checked(e.client.get(e.production_base + '/timelines/' + created['timeline_snapshot']['id'], headers=e.headers))
    assert original['timeline']['duration_ms'] == 20000 and original['version'] == 1
    assert original['comic_handoff_origin']['receipt_id'] == created['id']
    assert checked(e.client.post(e.handoff_base, headers=e.headers, json=value))['id'] == created['id']
    assert counts(e) == (2, 1, 1)
    (tmp_path / 'http-contract.json').write_text(json.dumps({'prefix': e.prefix,
        'request': body, 'preview_response': data, 'confirm': value, 'created': created,
        'readback': readback, 'original_timeline': original}, ensure_ascii=False, indent=2), encoding='utf8')


def test_four_explicit_ordered_pages_use_original_timeline_and_exact_assets(handoff_http):
    e = handoff_http
    pages = [approved_page(e) for _ in range(4)]
    body = request([pages[2], pages[0], pages[3], pages[1]])
    for selection, dwell in zip(body['pages'], [1000, 2000, 3000, 4000]): selection['duration_ms'] = dwell
    value = intent(e, body, 'ordered-four')
    result = checked(e.client.post(e.handoff_base, headers=e.headers, json=value))
    timeline = result['timeline']['timeline']
    clips = timeline['tracks'][0]['clips']
    assert timeline['schema_version'] == 2 and timeline['duration_ms'] == 10000
    assert [c['start_ms'] for c in clips] == [0, 1000, 3000, 6000]
    assert [c['out_ms'] for c in clips] == [1000, 2000, 3000, 4000]
    assert [c['source_snapshot']['id'] for c in clips] == [s['asset_id'] for s in result['steps']]
    assert [p['source']['id'] for p in result['preview']['pages']] == [p['id'] for p in body['pages']]
    assert all(c['in_ms'] == 0 and not c['include_audio'] for c in clips)
    assert counts(e) == (4, 1, 1)


@pytest.mark.parametrize('action', ['resume', 'cancel'])
def test_partial_native_write_requires_explicit_versioned_recovery(handoff_http, monkeypatch, action):
    e = handoff_http
    value = intent(e, request([approved_page(e), approved_page(e)]), 'partial')
    original, calls = e.assets.create, 0
    def fail_second(*args, **kwargs):
        nonlocal calls
        calls += 1
        if calls == 2: raise OSError('private-canary: C:/private/source and opaque-session')
        return original(*args, **kwargs)
    monkeypatch.setattr(e.assets, 'create', fail_second)
    rejected(e.client.post(e.handoff_base, headers=e.headers, json=value), 503, 'COMIC_HANDOFF_OUTCOME_UNKNOWN')
    monkeypatch.setattr(e.assets, 'create', original)
    observed = checked(e.client.get(e.handoff_base + '/partial', headers=e.headers))
    assert observed['status'] == 'PLANNED' and observed['version'] == 2
    assert [s['state'] for s in observed['steps']] == ['READY', 'PENDING']
    assert counts(e) == (1, 0, 1)
    assert checked(e.client.post(e.handoff_base, headers=e.headers, json=value)) == observed
    assert counts(e) == (1, 0, 1)
    rejected(e.client.post(e.handoff_base + '/partial/' + action, headers=e.headers,
                           json={'expected_version': 1}), 409, 'STUDIO_PRODUCTION_VERSION_CONFLICT')
    result = checked(e.client.post(e.handoff_base + '/partial/' + action, headers=e.headers,
                                   json={'expected_version': observed['version']}))
    if action == 'resume':
        assert result['status'] == 'DRAFT_CREATED' and counts(e) == (2, 1, 1)
        assert result['steps'][0]['asset_id'] == observed['steps'][0]['asset_id']
    else:
        assert result['status'] == 'CANCELLED' and counts(e) == (1, 0, 1)
        rejected(e.client.post(e.handoff_base + '/partial/resume', headers=e.headers,
                               json={'expected_version': result['version']}), 422)
        assert counts(e) == (1, 0, 1)


def test_lost_reply_after_actual_timeline_commit_is_read_back_without_replay(handoff_http, monkeypatch):
    e = handoff_http
    value = intent(e, request([approved_page(e)]), 'lost-reply')
    original, armed = e.store.transaction, True
    @contextmanager
    def lost_reply(*args, **kwargs):
        nonlocal armed
        lost = False
        with original(*args, **kwargs) as state:
            yield state
            if armed and any(r['status'] == 'DRAFT_CREATED' for r in state['collections'].get('comic_timeline_handoffs_v1', {}).values()):
                armed = False; lost = True
        if lost: raise OSError('private-canary: committed response lost')
    monkeypatch.setattr(e.store, 'transaction', lost_reply)
    rejected(e.client.post(e.handoff_base, headers=e.headers, json=value), 503, 'COMIC_HANDOFF_OUTCOME_UNKNOWN')
    assert not armed and counts(e) == (1, 1, 1)
    observed = checked(e.client.get(e.handoff_base + '/lost-reply', headers=e.headers))
    assert observed['status'] == 'DRAFT_CREATED'
    assert checked(e.client.post(e.handoff_base, headers=e.headers, json=value))['id'] == observed['id']
    assert counts(e) == (1, 1, 1)


def test_readonly_404_never_retries_a_failed_intent_write(handoff_http, monkeypatch):
    e = handoff_http
    value = intent(e, request([approved_page(e)]), 'before-commit')
    original = e.store.transaction
    @contextmanager
    def fail_commit(*args, **kwargs):
        with original(*args, **kwargs) as state:
            yield state
            if state['collections'].get('comic_timeline_handoffs_v1'):
                raise OSError('private-canary: no intent commit')
    monkeypatch.setattr(e.store, 'transaction', fail_commit)
    rejected(e.client.post(e.handoff_base, headers=e.headers, json=value), 503)
    monkeypatch.setattr(e.store, 'transaction', original)
    before = copy.deepcopy(e.store.read(e.nid, e.scope))
    for _ in range(2): rejected(e.client.get(e.handoff_base + '/before-commit', headers=e.headers), 404)
    assert counts(e) == (0, 0, 0) and e.store.read(e.nid, e.scope) == before
    # An explicit POST of the SAME immutable ID/body is the only new write here.
    assert checked(e.client.post(e.handoff_base, headers=e.headers, json=value))['status'] == 'DRAFT_CREATED'
    assert counts(e) == (1, 1, 1)


def test_real_source_edit_after_preview_invalidates_confirmation(handoff_http):
    e = handoff_http
    page = approved_page(e)
    value = intent(e, request([page]), 'stale')
    edited = {**copy.deepcopy(page[0]['document']), 'title': 'Explicit edit after preview',
              'expected_version': page[0]['version']}
    saved = checked(e.client.put(e.comic_base + '/records/' + page[0]['id'], headers=e.headers, json=edited))
    assert saved['version'] == page[0]['version'] + 1
    before = copy.deepcopy(e.store.read(e.nid, e.scope))
    rejected(e.client.post(e.handoff_base, headers=e.headers, json=value), 409)
    assert counts(e) == (0, 0, 0) and before == e.store.read(e.nid, e.scope)


def test_all_five_routes_require_original_host_and_reject_cross_origin(handoff_http):
    e = handoff_http
    value = intent(e, request([approved_page(e)]))
    before = copy.deepcopy(e.store.read(e.nid, e.scope))
    for headers, status in [({}, 401), ({'X-Session-Token': 'forged'}, 401),
                            ({**e.headers, 'Origin': 'https://untrusted.invalid'}, 403),
                            ({**e.headers, 'Forwarded': 'for=127.0.0.1'}, 403)]:
        for route in routes(e, value): rejected(call(e, route, headers), status)
    assert counts(e) == (0, 0, 0) and before == e.store.read(e.nid, e.scope)


def test_original_branch_and_actor_ownership_remain_enforced(handoff_http, monkeypatch):
    e = collaborative(handoff_http, monkeypatch)
    value = intent(e, request([approved_page(e)]))
    for route in routes(e, value):
        rejected(call(e, route, {**e.headers, 'X-Branch-ID': e.other_branch}), 403)
    e.viewer_headers = e.actor_headers(e.viewer)
    for route in routes(e, value):
        rejected(call(e, route, e.viewer_headers), 404 if route[0] == 'GET' or route[1].endswith('/preview') else 403)
    assert counts(e) == (0, 0, 0)
    e.headers = e.actor_headers(e.lead)
    result = checked(e.client.post(e.handoff_base, headers=e.headers, json=value))
    e.viewer_headers = e.actor_headers(e.viewer)
    rejected(e.client.get(e.handoff_base + '/' + value['request_id'], headers=e.viewer_headers), 404)
    assert counts(e) == (1, 1, 1) and result['status'] == 'DRAFT_CREATED'


def test_image_only_and_split_permissions_never_gain_timeline_write(handoff_http, monkeypatch):
    from app.authorization import PermissionAssignment, ModalityDomain
    from test_comic_independent import image_scope
    e = collaborative(handoff_http, monkeypatch)
    page = approved_page(e)
    value = intent(e, request([page]))
    auth_scope = image_scope(e)
    # The original source-free Comic route is available under IMAGE authority.
    listed = checked(e.client.get(e.comic_base + '/records', headers=e.headers))
    assert page[0]['id'] in [row['id'] for row in listed['items']]
    for route in routes(e, value): rejected(call(e, route), 403)
    e.authorization.assign_permission(PermissionAssignment('novel-read-' + e.role, e.lead, 'domain.read',
        ModalityDomain.NOVEL, auth_scope, e.lead))
    checked(e.client.post(e.handoff_base + '/preview', headers=e.headers, json=value['request']))
    for route in routes(e, value)[1:]: rejected(call(e, route), 404 if route[0] == 'GET' else 403)
    e.authorization.revoke_permission('novel-read-' + e.role, e.lead)
    e.authorization.assign_permission(PermissionAssignment('novel-write-' + e.role, e.lead, 'domain.write',
        ModalityDomain.NOVEL, auth_scope, e.lead))
    # Destination write without original NOVEL source-read is also insufficient.
    for route in routes(e, value): rejected(call(e, route), 403)
    assert counts(e) == (0, 0, 0)


def test_unpackaged_collaboration_membership_still_cannot_supply_host_authority(handoff_http, monkeypatch):
    e = handoff_http
    scoped(e, monkeypatch)
    checked(e.client.post(e.studio_base + '/activate', headers=e.headers))
    value = {'request_id': 'blocked-host', 'request': request([approved_page(e)]),
             'reviewed_preview_digest': '0' * 64, 'acknowledge_losses': True}
    for route in routes(e, value): rejected(call(e, route), 403, 'LOCAL_AI_HOST_AUTHORITY_UNAVAILABLE')
    assert counts(e) == (0, 0, 0)


def test_actual_native_commits_hold_original_session_and_authorization_leases(handoff_http, monkeypatch):
    e = collaborative(handoff_http, monkeypatch)
    value = intent(e, request([approved_page(e)]))
    depth = {'session': 0, 'authorization': 0}
    writes = []
    def tracing(original, name):
        @contextmanager
        def lease(*args, **kwargs):
            with original(*args, **kwargs) as result:
                depth[name] += 1
                try: yield result
                finally: depth[name] -= 1
        return lease
    monkeypatch.setattr(e.sessions, 'binding_lease', tracing(e.sessions.binding_lease, 'session'))
    repository = e.authorization.repository
    monkeypatch.setattr(repository, 'mutation', tracing(repository.mutation, 'authorization'))
    original_meta, original_transaction = e.assets._write_meta, e.store.transaction
    def write_meta(meta):
        assert min(depth.values()) > 0
        writes.append('asset')
        return original_meta(meta)
    @contextmanager
    def transaction(*args, **kwargs):
        changed = False
        with original_transaction(*args, **kwargs) as state:
            before = copy.deepcopy(state)
            yield state
            changed = state != before
            if changed: assert min(depth.values()) > 0
        if changed:
            assert min(depth.values()) > 0
            writes.append('scope')
    monkeypatch.setattr(e.assets, '_write_meta', write_meta)
    monkeypatch.setattr(e.store, 'transaction', transaction)
    result = checked(e.client.post(e.handoff_base, headers=e.headers, json=value))
    assert result['status'] == 'DRAFT_CREATED' and counts(e) == (1, 1, 1)
    assert writes.count('asset') == 1 and writes.count('scope') == 3
    assert depth == {'session': 0, 'authorization': 0}


@pytest.mark.parametrize('change,status', [('revoke', 401), ('same_binding_aba', 401), ('flag', 422)])
def test_preview_rechecks_host_after_actual_render_and_never_persists(handoff_http, monkeypatch, change, status):
    import app.experimental.comic_timeline_handoff as module
    e = handoff_http
    body = request([approved_page(e)])
    before = copy.deepcopy(e.store.read(e.nid, e.scope))
    original, rendered = module._render_page, []
    def revoke_after_render(*args, **kwargs):
        data = original(*args, **kwargs)
        rendered.append(data)
        if change == 'flag':
            monkeypatch.setenv('EXPERIMENTAL_FEATURES', ','.join(sorted(FEATURES - {'asset_lineage_v2'})))
        else:
            session = e.sessions.resolve(e.host).session
            e.sessions.revoke(e.host)
            if change == 'same_binding_aba': e.sessions.register(e.host, session)
        return data
    monkeypatch.setattr(module, '_render_page', revoke_after_render)
    rejected(e.client.post(e.handoff_base + '/preview', headers=e.headers, json=body), status)
    assert rendered and counts(e) == (0, 0, 0) and before == e.store.read(e.nid, e.scope)


def test_exception_responses_do_not_echo_raw_owner_errors(handoff_http, monkeypatch):
    e = handoff_http
    value = intent(e, request([approved_page(e)]))
    def fail(*args, **kwargs): raise ValueError('private-canary: C:/private/input?token=opaque-session')
    monkeypatch.setattr(e.assets, 'create', fail)
    rejected(e.client.post(e.handoff_base, headers=e.headers, json=value), 422)
    observed = checked(e.client.get(e.handoff_base + '/' + value['request_id'], headers=e.headers))
    assert observed['status'] == 'PLANNED' and counts(e) == (0, 0, 1)


def test_partial_receipt_recovery_rechecks_current_write_grants(handoff_http, monkeypatch):
    from app.authorization import AuthorizationScope, ScopeKind, PermissionAssignment, ModalityDomain
    e = collaborative(handoff_http, monkeypatch)
    value = intent(e, request([approved_page(e), approved_page(e)]), 'revoked-partial')
    original, calls = e.assets.create, 0
    def fail_second(*args, **kwargs):
        nonlocal calls
        calls += 1
        if calls == 2: raise OSError('private-canary: partial write')
        return original(*args, **kwargs)
    monkeypatch.setattr(e.assets, 'create', fail_second)
    rejected(e.client.post(e.handoff_base, headers=e.headers, json=value), 503)
    monkeypatch.setattr(e.assets, 'create', original)
    observed = checked(e.client.get(e.handoff_base + '/revoked-partial', headers=e.headers))
    assert counts(e) == (1, 0, 1) and observed['version'] == 2
    e.authorization.revoke_role(e.role, e.lead)
    auth_scope = AuthorizationScope(ScopeKind.BRANCH, e.workspace, e.nid, e.storyline, e.branch)
    e.authorization.assign_permission(PermissionAssignment('recover-read-' + e.role, e.lead, 'domain.read',
        ModalityDomain.NOVEL, auth_scope, e.lead))
    assert checked(e.client.get(e.handoff_base + '/revoked-partial', headers=e.headers)) == observed
    for action in ['resume', 'cancel']:
        rejected(e.client.post(e.handoff_base + '/revoked-partial/' + action, headers=e.headers,
                               json={'expected_version': 2}), 403)
    assert counts(e) == (1, 0, 1)
    e.authorization.assign_permission(PermissionAssignment('recover-write-' + e.role, e.lead, 'domain.write',
        ModalityDomain.NOVEL, auth_scope, e.lead))
    completed = checked(e.client.post(e.handoff_base + '/revoked-partial/resume', headers=e.headers,
                                      json={'expected_version': 2}))
    assert completed['steps'][0]['asset_id'] == observed['steps'][0]['asset_id']
    assert completed['status'] == 'DRAFT_CREATED' and counts(e) == (2, 1, 1)
