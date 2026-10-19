"""Whole-request/response limits with actual PNGs and mounted original owners."""
import copy
import json
from uuid import uuid4

from app.creative.production_execution_api import ComicHandoffRoute
from app.creative.workspace_api import is_independent_studio_route
from app.services.comic_page_origin import FEATURES
from test_comic_timeline_handoff_http import (
    mounted, prefix, client, handoff_http, approved_page, request, intent,
    checked, counts, rejected, routes, call,
)


def test_private_strict_json_and_bounded_typed_selections(handoff_http):
    e = handoff_http
    body = request([approved_page(e)])
    invalid = []
    for key, value in [('source_path', 'private-canary'), ('executable', 'private-canary'),
                       ('width', True), ('height', 351), ('fps', 24.5), ('title', 'private-canary\ninside')]:
        invalid.append({**copy.deepcopy(body), key: value})
    for key, value in [('duration_ms', True), ('duration_ms', 1.5), ('duration_ms', '1000'),
                       ('duration_ms', 600001), ('duration_ms', -1), ('version', False),
                       ('source_path', 'private-canary')]:
        changed = copy.deepcopy(body); changed['pages'][0][key] = value; invalid.append(changed)
    invalid += [{**body, 'pages': []}, {**body, 'pages': body['pages'] * 2}, {**body, 'pages': body['pages'] * 5}]
    total = copy.deepcopy(body); total['pages'] = [dict(body['pages'][0], id='page-' + str(i), duration_ms=200000) for i in range(4)]
    invalid.append(total)
    before = copy.deepcopy(e.store.read(e.nid, e.scope))
    for value in invalid:
        rejected(e.client.post(e.handoff_base + '/preview', headers=e.headers, json=value), 422, 'COMIC_HANDOFF_REQUEST_INVALID')
    payload = json.dumps(body)
    raw = ['{"private-canary":', '{"title":"private-canary","title":"duplicate"}',
           payload.replace('10000', 'NaN'), payload.replace('10000', 'Infinity'),
           'null', '[]', '[' * 1500 + '0' + ']' * 1500, b'\xff']
    for content in raw:
        rejected(e.client.post(e.handoff_base + '/preview', headers={**e.headers, 'Content-Type': 'application/json'},
                               content=content), 422, 'COMIC_HANDOFF_REQUEST_INVALID')
    assert counts(e) == (0, 0, 0) and e.store.read(e.nid, e.scope) == before


def test_confirm_and_recovery_require_explicit_ack_and_strict_cas(handoff_http):
    e = handoff_http
    value = intent(e, request([approved_page(e)]))
    before = copy.deepcopy(e.store.read(e.nid, e.scope))
    for key, changed in [('acknowledge_losses', False), ('acknowledge_losses', 1),
                         ('request_id', '../private-canary'), ('private-canary', 'private-canary')]:
        rejected(e.client.post(e.handoff_base, headers=e.headers, json={**value, key: changed}), 422, 'COMIC_HANDOFF_REQUEST_INVALID')
    without = dict(value); del without['acknowledge_losses']
    rejected(e.client.post(e.handoff_base, headers=e.headers, json=without), 422)
    for action in ['resume', 'cancel']:
        for invalid in [True, 1.5, '1', 0, 9]:
            rejected(e.client.post(e.handoff_base + '/missing/' + action, headers=e.headers,
                                   json={'expected_version': invalid}), 422, 'COMIC_HANDOFF_REQUEST_INVALID')
        rejected(e.client.post(e.handoff_base + '/missing/' + action, headers=e.headers,
                               json={'expected_version': 1, 'private-canary': 'private-canary'}), 422)
    rejected(e.client.post(e.handoff_base, headers=e.headers,
                           json={**value, 'reviewed_preview_digest': '0' * 64}), 409)
    assert counts(e) == (0, 0, 0) and before == e.store.read(e.nid, e.scope)


def test_stream_cap_uses_actual_bytes_and_get_cannot_carry_body(handoff_http):
    e = handoff_http
    before = copy.deepcopy(e.store.read(e.nid, e.scope))
    assert ComicHandoffRoute.MAX_BODY == 16 * 1024
    for declared in [None, '1', '9999999']:
        headers = {**e.headers, 'Content-Type': 'application/json'}
        if declared is not None: headers['Content-Length'] = declared
        def chunks():
            for _ in range(3): yield b'private-canary' + b'x' * 8192
        rejected(e.client.post(e.handoff_base + '/preview', headers=headers, content=chunks()),
                 413, 'COMIC_HANDOFF_REQUEST_LIMIT')
    rejected(e.client.post(e.handoff_base + '/preview', headers={**e.headers, 'Content-Type': 'text/plain'},
                           content='private-canary'), 415, 'COMIC_HANDOFF_JSON_REQUIRED')
    rejected(e.client.request('GET', e.handoff_base + '/missing', headers=e.headers, content='private-canary'),
             422, 'COMIC_HANDOFF_REQUEST_INVALID')
    assert counts(e) == (0, 0, 0) and before == e.store.read(e.nid, e.scope)


def test_real_rendered_png_and_serialized_response_budgets_reject_whole_preview(handoff_http, monkeypatch):
    e = handoff_http
    body = request([approved_page(e), approved_page(e)])
    before = copy.deepcopy(e.store.read(e.nid, e.scope))
    assert ComicHandoffRoute.MAX_PNG == 8 * 1024 * 1024
    assert ComicHandoffRoute.MAX_RESPONSE == 12 * 1024 * 1024
    # Lower the HTTP thresholds only; original renderer, PNG decoder, page
    # budget, pins, hashes and original publication admission remain real.
    for field, code in [('MAX_PNG', 'COMIC_HANDOFF_PREVIEW_PNG_LIMIT'),
                        ('MAX_RESPONSE', 'COMIC_HANDOFF_RESPONSE_LIMIT')]:
        with monkeypatch.context() as patch:
            patch.setattr(ComicHandoffRoute, field, 1)
            rejected(e.client.post(e.handoff_base + '/preview', headers=e.headers, json=body), 413, code)
        assert counts(e) == (0, 0, 0) and before == e.store.read(e.nid, e.scope)


def test_response_limit_after_real_write_requires_exact_id_readback(handoff_http, monkeypatch):
    e = handoff_http
    value = intent(e, request([approved_page(e)]), 'response-cap')
    with monkeypatch.context() as patch:
        patch.setattr(ComicHandoffRoute, 'MAX_RESPONSE', 1)
        rejected(e.client.post(e.handoff_base, headers=e.headers, json=value), 413, 'COMIC_HANDOFF_RESPONSE_LIMIT')
    assert counts(e) == (1, 1, 1)
    observed = checked(e.client.get(e.handoff_base + '/response-cap', headers=e.headers))
    assert observed['status'] == 'DRAFT_CREATED'
    assert checked(e.client.post(e.handoff_base, headers=e.headers, json=value))['id'] == observed['id']
    assert counts(e) == (1, 1, 1)


def test_every_required_flag_and_v1_override_fail_closed_on_five_routes(handoff_http, monkeypatch):
    e = handoff_http
    value = intent(e, request([approved_page(e)]))
    before = copy.deepcopy(e.store.read(e.nid, e.scope))
    for removed in [*sorted(FEATURES), 'acceptance']:
        with monkeypatch.context() as patch:
            if removed == 'acceptance': patch.setenv('V1_ACCEPTANCE_MODE', 'true')
            else: patch.setenv('EXPERIMENTAL_FEATURES', ','.join(sorted(FEATURES - {removed})))
            for route in routes(e, value): rejected(call(e, route), 404, 'EXPERIMENTAL_FEATURE_DISABLED')
    assert counts(e) == (0, 0, 0) and before == e.store.read(e.nid, e.scope)


def test_missing_handoff_owner_never_falls_back_to_general_production(handoff_http, monkeypatch):
    e = handoff_http
    value = intent(e, request([approved_page(e)]))
    monkeypatch.setattr(e.production, 'comic_handoff', None)
    for route in routes(e, value): rejected(call(e, route), 404, 'COMIC_HANDOFF_UNAVAILABLE')
    assert counts(e) == (0, 0, 0)


def test_observation_and_confirm_do_not_activate_missing_project_identity(handoff_http):
    e = handoff_http
    value = intent(e, request([approved_page(e)]))
    nid = checked(e.client.post(e.prefix + '/novels', json={'id': 'http-unactivated-' + uuid4().hex,
                                                         'title': 'Unactivated owner'}), 201)['id']
    marker = e.root / 'novels' / nid / 'creative_project_v2.json'
    assert not marker.exists()
    scope = {'mode': 'local', 'novel_id': nid}
    before = copy.deepcopy(e.store.read(nid, scope))
    for method, path, body in routes(e, value):
        rejected(call(e, (method, path.replace(e.nid, nid), body)), 404)
    assert not marker.exists() and before == e.store.read(nid, scope) and counts(e) == (0, 0, 0)


def test_only_five_closed_handoff_route_shapes_gain_middleware_admission():
    base = '/api/projects/project/studio/production/comic-handoffs'
    valid = [('POST', base), ('POST', base + '/preview'), ('GET', base + '/request-1'),
             ('GET', base + '/preview'), ('POST', base + '/request-1/resume'),
             ('POST', base + '/request-1/cancel')]
    assert all(is_independent_studio_route(method, path) for method, path in valid)
    invalid = [('GET', base), ('PUT', base), ('DELETE', base + '/request-1'),
               ('POST', base + '/request-1'), ('POST', base + '/request-1/execute'),
               ('POST', base + '/request-1/resume/extra'), ('GET', base + '/request-1/cancel'),
               ('POST', base + '//cancel'), ('POST', base + '/private.canary/resume'),
               ('POST', base + '/' + 'a' * 81 + '/resume')]
    assert not any(is_independent_studio_route(method, path) for method, path in invalid)
