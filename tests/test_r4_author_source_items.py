"""U08 individual source selection uses the real request builder/dispatch guard."""
import copy
import json
import pytest
from app.author_context_sources import apply_source_controls, fingerprint
from app.source_privacy import content_digest, review_source_privacy
from test_r4_author_context import rig, preview, generate, url
from test_r4_author_scope_variants import scope


def prepare(rig):
    rig.sources['characters'] = [{'id': 'removed', 'name': '排除人物', 'personality': 'EXCLUDED_CANARY'},
                                 {'id': 'kept', 'name': '保留人物', 'personality': 'KEPT_CANARY'}]
    rig.sources['story_state'] = {'active_characters': ['removed', 'kept'], 'secret_copy': 'EXCLUDED_CANARY'}
    rig.sources['summaries'] = [{'chapter': 1, 'summary': 'EXCLUDED_CANARY'}]
    rig.sources['novel']['long_term_summary'] = 'EXCLUDED_CANARY'
    rig.sources['style_profile'] = {'rules': 'EXCLUDED_CANARY'}
    body = {**rig.body, 'request_scope': scope()}
    value = preview(rig, body)
    removed = next(row for row in value['source_manifest']['items'] if row['label'] == '排除人物')
    body['request_scope']['source_items'] = [{key: removed[key] for key in ['key', 'source_digest']} | {'include': False}]
    return body, removed


def test_single_source_exclusion_removes_all_unknown_derivatives_but_keeps_other_direct_record(rig):
    body, removed = prepare(rig); value = preview(rig, body)
    assert 'EXCLUDED_CANARY' not in json.dumps(value['request'], ensure_ascii=False)
    assert 'KEPT_CANARY' in value['request']['prompt'] and value['source_characters'] == len('selection')
    assert value['source_manifest']['dependent_context_omitted']
    assert value['scope_effects']['references_omitted_for_source_isolation']
    assert value['source_manifest']['items'][0]['pinned'] and not value['source_manifest']['items'][0]['included']
    assert generate(rig, value, body).json()['status'] == 'COMPLETED'
    assert rig.state.sent == [value['request']]
    assert removed['key'] not in json.dumps(rig.state.sent)  # review identity is not provider context


@pytest.mark.parametrize('mutation', ['change', 'remove', 'revoke', 'flag'])
def test_source_pin_current_authority_is_rechecked_at_actual_dispatch(rig, monkeypatch, mutation):
    body, _ = prepare(rig); value = preview(rig, body)
    def mutate():
        if mutation == 'change': rig.sources['characters'][0]['personality'] = 'CHANGED'
        elif mutation == 'remove': rig.sources['characters'].pop(0)
        elif mutation == 'revoke': rig.state.permitted = False
        else: monkeypatch.setenv('V1_ACCEPTANCE_MODE', 'true')
    rig.state.before_send = mutate
    assert generate(rig, value, body).json()['status'] == 'FAILED'
    assert not rig.state.sent


def test_pin_changed_even_if_numeric_version_unchanged_rejects_preview_and_omits_error_content(rig):
    body, removed = prepare(rig)
    rig.sources['characters'][0]['personality'] = 'DO_NOT_ECHO_CHANGED_CONTENT'
    r = rig.client.post(url('preview'), json=body, headers=rig.headers)
    assert r.status_code == 409
    assert 'DO_NOT_ECHO' not in r.text and removed['key'] not in r.text


def test_explicit_include_pin_uses_content_fingerprint_without_inventing_version(rig):
    body, _ = prepare(rig); body['request_scope']['source_items'][0]['include'] = True
    value = preview(rig, body); row = value['source_manifest']['items'][0]
    assert row['included'] and row['pinned'] and row['version'] is None and row['version_state'] == 'CONTENT_DIGEST_ONLY'
    assert not value['source_manifest']['dependent_context_omitted'] and 'EXCLUDED_CANARY' in value['request']['prompt']


def test_cloud_ineligible_sources_never_enter_visible_source_catalog(rig):
    rig.state.cloud = True; rig.body['profile'] = 'QUALITY'
    review_source_privacy(rig.chapter, None, 'synthetic', 'CLOUD_ALLOWED', 1, content_digest(rig.chapter))
    rig.sources['characters'] = [{'id': 'PRIVATE_ID', 'name': 'PRIVATE_LABEL', 'privacy_level': 'LOCAL_ONLY'}]
    rig.sources['story_state'] = {'active_characters': ['PRIVATE_ID']}
    response = rig.client.post(url('preview'), json={**rig.body, 'request_scope': scope()}, headers=rig.headers)
    # Original whole-project source policy is stricter than the item filter;
    # adding a control must not bypass that existing cloud prohibition.
    assert response.status_code == 409 and not rig.state.sent
    assert 'PRIVATE_ID' not in response.text and 'PRIVATE_LABEL' not in response.text
    context = rig.manager.contexts.for_chapter('n:1', 'Concise', True, 'continue')
    _, manifest = apply_source_controls(context, 'n')
    assert manifest['items'] == []


def test_any_potential_derived_context_is_removed_including_unknown_context_keys():
    base = {'chapter': 1, 'characters': [{'id': 'x', 'name': 'X', 'text': 'CANARY'}, {'id': 'y', 'name': 'Y'}]}
    _, catalog = apply_source_controls(base, 'n'); source = catalog['items'][0]
    for key in ['lore_memory', 'narrative_context', 'context_policy', 'context_pack_v2', 'long_term_summary', 'novel', 'must_include', 'chapter_goal', 'unknown_derived_extension']:
        base[key] = {'nested': 'CANARY'}
    filtered, manifest = apply_source_controls(base, 'n', [{'key': source['key'], 'source_digest': source['source_digest'], 'include': False}])
    assert 'CANARY' not in json.dumps(filtered) and 'y' in json.dumps(filtered)
    assert manifest['dependent_context_omitted'] and base['characters'][0]['id'] == 'x'


def test_identical_ids_in_other_project_do_not_reuse_pin():
    context = {'locations': [{'id': 'same', 'name': 'Place'}]}
    _, a = apply_source_controls(context, 'a'); _, b = apply_source_controls(context, 'b')
    assert a['items'][0]['key'] != b['items'][0]['key']
    with pytest.raises(ValueError, match='UNAVAILABLE_OR_CHANGED'):
        apply_source_controls(context, 'b', [{'key': a['items'][0]['key'], 'source_digest': a['items'][0]['source_digest'], 'include': False}])


@pytest.mark.parametrize('bad', ['duplicate', 'unknown', 'malformed'])
def test_invalid_controls_reject_without_dispatch(rig, bad):
    body, _ = prepare(rig)
    if bad == 'duplicate': body['request_scope']['source_items'] *= 2
    elif bad == 'unknown': body['request_scope']['source_items'][0]['key'] = 'f' * 64
    else: body['request_scope']['source_items'][0]['include'] = 'false'
    r = rig.client.post(url('preview'), json=body, headers=rig.headers)
    assert r.status_code in {409, 422} and not rig.state.sent
